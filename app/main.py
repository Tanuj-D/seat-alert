import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from html import escape

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, mailer, scraper
from app.db import Subscriber, Watch, as_utc, get_session, init_db, utcnow
from app.ratelimit import RateLimiter

log = logging.getLogger(__name__)

create_watch_limiter = RateLimiter(config.CREATE_WATCH_LIMIT_PER_MINUTE, 60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Uvicorn only sets up its own loggers; without this, app logs (including
    # emails printed in local mode) are silently dropped.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()
    yield


app = FastAPI(title="UNC Seat Alert", lifespan=lifespan)


# --- Schemas -----------------------------------------------------------------

class SectionOut(BaseModel):
    subject: str
    catalog_number: str
    section: str
    class_number: str
    title: str
    term: str
    schedule: str
    instruction_mode: str
    available_seats: int


class WatchIn(BaseModel):
    email: EmailStr
    term: str = Field(min_length=4, max_length=32, examples=["2027 Spring"])
    subject: str = Field(min_length=2, max_length=8, examples=["COMP"])
    catalog_number: str = Field(min_length=1, max_length=8, examples=["211"])
    section: str = Field(min_length=1, max_length=8, examples=["001"])

    @field_validator("subject")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class WatchOut(BaseModel):
    id: int
    term: str
    subject: str
    catalog_number: str
    section: str
    last_seats: int | None


class CreateWatchOut(BaseModel):
    watch: WatchOut
    verified: bool
    message: str


# --- Helpers -----------------------------------------------------------------

def subscriber_by_token(session: Session, token: str) -> Subscriber:
    sub = session.scalar(select(Subscriber).where(Subscriber.token == token))
    if sub is None:
        raise HTTPException(404, "Invalid or expired link")
    return sub


def maybe_send_verification(session: Session, sub: Subscriber) -> None:
    """Send a confirmation email, at most once per cooldown window per address."""
    cooldown = timedelta(seconds=config.VERIFY_EMAIL_COOLDOWN_SECONDS)
    if sub.verification_sent_at and utcnow() - as_utc(sub.verification_sent_at) < cooldown:
        return
    try:
        mailer.mailer.send(mailer.verification_email(sub.email, sub.token))
    except Exception:
        log.exception("Failed to send verification email to %s", sub.email)
        return
    sub.verification_sent_at = utcnow()
    session.commit()


def html_page(title: str, message: str, status: int = 200) -> HTMLResponse:
    body = (f"<!doctype html><meta charset=utf-8><title>{escape(title)}</title>"
            "<body style='font-family:system-ui;max-width:32rem;margin:4rem auto;padding:0 1rem'>"
            f"<h1>{escape(title)}</h1><p>{escape(message)}</p></body>")
    return HTMLResponse(body, status_code=status)


# --- Routes ------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/sections", response_model=list[SectionOut])
def get_sections(term: str, subject: str, catalog_number: str):
    try:
        sections = scraper.fetch_sections(term, subject, catalog_number)
    except httpx.HTTPError:
        raise HTTPException(502, "UNC class search is unavailable right now")
    return [SectionOut(**s.__dict__) for s in sections]


@app.post("/api/watches", response_model=CreateWatchOut, status_code=201,
          dependencies=[Depends(create_watch_limiter.dependency)])
def create_watch(body: WatchIn, session: Session = Depends(get_session)):
    # Make sure the section exists before watching it.
    try:
        sections = scraper.fetch_sections(body.term, body.subject, body.catalog_number)
    except httpx.HTTPError:
        raise HTTPException(502, "UNC class search is unavailable right now")
    match = next((s for s in sections if s.section == body.section), None)
    if match is None:
        raise HTTPException(
            404, f"No section {body.section} of {body.subject} {body.catalog_number} "
                 f"in {body.term}")

    sub = session.scalar(select(Subscriber).where(Subscriber.email == body.email))
    if sub is None:
        sub = Subscriber(email=body.email)
        session.add(sub)
        session.flush()

    count = session.scalar(select(func.count(Watch.id)).where(Watch.subscriber_id == sub.id))
    if count >= config.MAX_WATCHES_PER_USER:
        raise HTTPException(400, f"You can watch up to {config.MAX_WATCHES_PER_USER} sections")

    # Save the term UNC reports (e.g. "2027 Spring"), not what the user typed:
    # UNC ignores terms it doesn't recognize, so "Spring" would still match.
    watch = Watch(subscriber_id=sub.id, term=match.term, subject=body.subject,
                  catalog_number=body.catalog_number, section=body.section,
                  last_seats=match.available_seats)
    session.add(watch)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "You're already watching this section")

    if sub.verified:
        message = "You're all set. We'll email you when a seat opens."
    else:
        maybe_send_verification(session, sub)
        message = "Check your inbox and confirm your email to start getting alerts."
    return CreateWatchOut(watch=WatchOut.model_validate(watch, from_attributes=True),
                          verified=sub.verified, message=message)


@app.get("/api/verify", response_class=HTMLResponse)
def verify_email(token: str, session: Session = Depends(get_session)):
    sub = session.scalar(select(Subscriber).where(Subscriber.token == token))
    if sub is None:
        return html_page("Link not valid", "This confirmation link is invalid or expired.", 404)
    if not sub.verified:
        sub.verified_at = utcnow()
        session.commit()
    return html_page("Email confirmed",
                     "You're all set. We'll email you as soon as a seat opens.")


@app.get("/api/watches", response_model=list[WatchOut])
def list_watches(token: str = Query(...), session: Session = Depends(get_session)):
    return subscriber_by_token(session, token).watches


@app.delete("/api/watches/{watch_id}", status_code=204)
def delete_watch(watch_id: int, token: str = Query(...),
                 session: Session = Depends(get_session)):
    sub = subscriber_by_token(session, token)
    watch = session.get(Watch, watch_id)
    if watch is None or watch.subscriber_id != sub.id:
        raise HTTPException(404, "Watch not found")
    session.delete(watch)
    session.commit()


@app.get("/api/unsubscribe/{watch_id}", response_class=HTMLResponse)
def unsubscribe(watch_id: int, token: str, session: Session = Depends(get_session)):
    """Link in alert emails. A GET so it works with one click from any mail app."""
    sub = session.scalar(select(Subscriber).where(Subscriber.token == token))
    watch = session.get(Watch, watch_id)
    if sub is None or watch is None or watch.subscriber_id != sub.id:
        return html_page("Already removed", "You're no longer watching this section.")
    course = watch.course
    session.delete(watch)
    session.commit()
    return html_page("Unsubscribed", f"You'll no longer get alerts for {course}.")
