import os
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# SQLite locally; set DATABASE_URL to a Postgres URL in production.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./seat_alert.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Watch(Base):
    """One user watching one course section."""

    __tablename__ = "watches"
    __table_args__ = (UniqueConstraint("email", "term", "subject", "catalog_number", "section"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    term: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(8))
    catalog_number: Mapped[str] = mapped_column(String(8))
    section: Mapped[str] = mapped_column(String(8))
    last_seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
