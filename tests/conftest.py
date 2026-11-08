import os
import tempfile
from pathlib import Path

import pytest

# Point the app at a throwaway database before any app module is imported.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SMTP_HOST"] = ""  # never send real email from tests

from app import mailer, scraper  # noqa: E402
from app.db import Base, SessionLocal, Subscriber, engine, utcnow  # noqa: E402
from app.main import create_watch_limiter  # noqa: E402
from app.scraper import parse_sections  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
COMP211_HTML = (FIXTURES / "comp211_spring2027.html").read_text()


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    create_watch_limiter.reset()
    # By default, "UNC" returns the saved COMP 211 page (001 full, 002 has 40 seats).
    monkeypatch.setattr(scraper, "fetch_sections", lambda *_: parse_sections(COMP211_HTML))
    yield


@pytest.fixture(autouse=True)
def outbox(monkeypatch) -> list[mailer.Email]:
    fake = mailer.ConsoleMailer()
    monkeypatch.setattr(mailer, "mailer", fake)
    return fake.sent


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def comp211_html() -> str:
    return COMP211_HTML


@pytest.fixture
def verified_subscriber(session) -> Subscriber:
    sub = Subscriber(email="a@unc.edu", verified_at=utcnow())
    session.add(sub)
    session.commit()
    return sub
