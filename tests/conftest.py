import os
import tempfile
from pathlib import Path

import pytest

# Point the app at a throwaway database before any app module is imported.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

from app.db import Base, SessionLocal, engine  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def comp211_html() -> str:
    return (FIXTURES / "comp211_spring2027.html").read_text()
