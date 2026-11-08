import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config, mailer, scraper
from app.cache import TTLCache
from app.checker import run_check_once
from app.db import Subscriber, Watch, as_utc, get_session, init_db, utcnow
from app.ratelimit import RateLimiter

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"

create_watch_limiter = RateLimiter(config.CREATE_WATCH_LIMIT_PER_MINUTE, 60)
search_limiter = RateLimiter(config.SEARCH_LIMIT_PER_MINUTE, 60)
sections_cache = TTLCache(ttl_seconds=60)
options_cache = TTLCache(ttl_seconds=3600)


async def checker_loop() -> None:
    """Runs the seat checker inside the web process (when EMBEDDED_CHECKER is on)."""
    while True:
        try:
            sent = await asyncio.to_thread(run_check_once)
            log.info("Check complete, %d alerts sent", sent)
        except Exception:
            log.exception("Seat check failed")
        await asyncio.sleep(config.CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Uvicorn only sets up its own loggers; without this, app logs (including
    # emails printed in local mode) are silently dropped.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()
    task = asyncio.create_task(checker_loop()) if config.EMBEDDED_CHECKER else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="UNC Seat Alert", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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
    title: str | None
    schedule: str | None
    last_seats: int | None
    last_checked_at: datetime | None


class SearchOptionsOut(BaseModel):
    terms: list[str]
    subjects: list[str]


class CreateWatchOut(BaseModel):
    watch: WatchOut
    verified: bool
    message: str


# --- Helpers -----------------------------------------------------------------

def lookup_sections(term: str, subject: str, catalog_number: str) -> list[scraper.Section]:
    """Fetch sections from UNC, cached briefly. Raises 502 if UNC is unreachable."""
    key = (term.strip(), subject.strip().upper(), catalog_number.strip())
    try:
        return sections_cache.get_or_set(key, lambda: scraper.fetch_sections(*key))
    except httpx.HTTPError:
        raise HTTPException(502, "UNC class search is unavailable right now")


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


def html_page(title: str, message: str, status: int = 200,
              link: tuple[str, str] | None = None) -> HTMLResponse:
    href, label = link or ("/", "Back to UNC Seat Alert")
    body = (
        "<!doctype html><html lang=en><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)} · UNC Seat Alert</title>"
        "<link rel=icon href='/static/icon.svg' type='image/svg+xml'>"
        "<link rel=stylesheet href='/static/app.css'>"
        "<main class='page narrow'>"
        "<a class=brand href='/' style='margin-bottom:20px'>"
        "<img src='/static/icon.svg' alt=''><span>UNC Seat Alert</span></a>"
        "<div class=card>"
        f"<h1>{escape(title)}</h1><p>{escape(message)}</p>"
        f"<a class='btn' href='{escape(href)}'>{escape(label)}</a>"
        "</div></main></html>"
    )
    return HTMLResponse(body, status_code=status)


# --- Pages -------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manage", include_in_schema=False)
def manage_page():
    return FileResponse(STATIC_DIR / "manage.html")


# --- API ---------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/options", response_model=SearchOptionsOut)
def get_search_options():
    """Terms and subject codes for the search form. Cached, so no rate limit."""
    try:
        return options_cache.get_or_set("options", scraper.fetch_search_options)
    except httpx.HTTPError:
        raise HTTPException(502, "UNC class search is unavailable right now")


@app.get("/api/sections", response_model=list[SectionOut],
         dependencies=[Depends(search_limiter.dependency)])
def get_sections(term: str, subject: str, catalog_number: str):
    sections = lookup_sections(term, subject, catalog_number)
    return [SectionOut(**s.__dict__) for s in sections]


@app.post("/api/watches", response_model=CreateWatchOut, status_code=201,
          dependencies=[Depends(create_watch_limiter.dependency)])
def create_watch(body: WatchIn, session: Session = Depends(get_session)):
    # Make sure the section exists before watching it.
    sections = lookup_sections(body.term, body.subject, body.catalog_number)
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
                  catalog_number=body.catalog_number, section=body.section)
    watch.update_from(match)
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
                     "You're all set. We'll email you as soon as a seat opens.",
                     link=(f"/manage?token={sub.token}", "See your watched classes"))


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
    return html_page("Unsubscribed", f"You'll no longer get alerts for {course}.",
                     link=(f"/manage?token={sub.token}", "See your other watched classes"))
