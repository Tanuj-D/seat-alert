import secrets
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import (DateTime, ForeignKey, Integer, String, UniqueConstraint,
                        create_engine)
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session, mapped_column,
                            relationship, sessionmaker)

from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """SQLite drops timezone info, so treat naive datetimes as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def new_token() -> str:
    return secrets.token_urlsafe(32)


class Subscriber(Base):
    """A person, identified by email. They only get alerts once verified.

    `token` is a secret sent only to their inbox. It confirms their email and
    is required to view or delete their watches, so knowing someone's email
    address isn't enough to mess with their alerts.
    """

    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=new_token)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watches: Mapped[list["Watch"]] = relationship(
        back_populates="subscriber", cascade="all, delete-orphan")

    @property
    def verified(self) -> bool:
        return self.verified_at is not None


class Watch(Base):
    """One subscriber watching one course section."""

    __tablename__ = "watches"
    __table_args__ = (
        UniqueConstraint("subscriber_id", "term", "subject", "catalog_number", "section"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int] = mapped_column(
        ForeignKey("subscribers.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(8))
    catalog_number: Mapped[str] = mapped_column(String(8))
    section: Mapped[str] = mapped_column(String(8))
    last_seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subscriber: Mapped[Subscriber] = relationship(back_populates="watches")

    @property
    def course(self) -> str:
        return f"{self.subject} {self.catalog_number}-{self.section}"


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
