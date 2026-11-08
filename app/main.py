from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import scraper
from app.db import Watch, get_session, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="UNC Seat Alert", lifespan=lifespan)


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
    term: str = Field(examples=["2027 Spring"])
    subject: str = Field(min_length=2, max_length=8, examples=["COMP"])
    catalog_number: str = Field(min_length=1, max_length=8, examples=["211"])
    section: str = Field(min_length=1, max_length=8, examples=["001"])


class WatchOut(WatchIn):
    id: int
    last_seats: int | None


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


@app.post("/api/watches", response_model=WatchOut, status_code=201)
def create_watch(body: WatchIn, session: Session = Depends(get_session)):
    watch = Watch(**body.model_dump() | {"subject": body.subject.upper()})
    session.add(watch)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "You're already watching this section")
    return watch


@app.get("/api/watches", response_model=list[WatchOut])
def list_watches(email: EmailStr = Query(...), session: Session = Depends(get_session)):
    return session.scalars(select(Watch).where(Watch.email == email)).all()


@app.delete("/api/watches/{watch_id}", status_code=204)
def delete_watch(watch_id: int, email: EmailStr = Query(...),
                 session: Session = Depends(get_session)):
    watch = session.get(Watch, watch_id)
    if watch is None or watch.email != email:
        raise HTTPException(404, "Watch not found")
    session.delete(watch)
    session.commit()
