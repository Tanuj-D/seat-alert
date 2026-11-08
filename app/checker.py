"""Check every watched section and send alerts when seats open up."""

import logging
import time
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import config, mailer
from app.db import SessionLocal, Subscriber, Watch, utcnow
from app.scraper import Section, fetch_sections

log = logging.getLogger(__name__)

Fetcher = Callable[[str, str, str], list[Section]]
Notifier = Callable[[Watch, Section], None]


def email_notifier(watch: Watch, section: Section) -> None:
    sub = watch.subscriber
    mailer.mailer.send(mailer.seat_alert_email(
        to=sub.email, course=watch.course, title=section.title,
        schedule=section.schedule, seats=section.available_seats,
        unsubscribe_link=f"{config.BASE_URL}/api/unsubscribe/{watch.id}?token={sub.token}",
        manage_link=f"{config.BASE_URL}/manage?token={sub.token}"))


def check_watches(session: Session, fetch: Fetcher = fetch_sections,
                  notify: Notifier = email_notifier, delay: float = 0.0) -> int:
    """Run one pass over all verified watches. Returns how many alerts were sent.

    Watches are grouped by course so each course page is fetched once, no
    matter how many people watch it. An alert fires only when a section goes
    from 0 seats (or unknown) to at least 1, so users aren't spammed every run.
    If an alert fails to send, the seat count isn't saved, so the next run retries.
    """
    watches = session.scalars(
        select(Watch)
        .join(Subscriber)
        .where(Subscriber.verified_at.is_not(None))
        .options(joinedload(Watch.subscriber))
    )
    groups: dict[tuple[str, str, str], list[Watch]] = defaultdict(list)
    for w in watches:
        groups[(w.term, w.subject, w.catalog_number)].append(w)

    sent = 0
    for i, ((term, subject, catalog), group) in enumerate(groups.items()):
        if i and delay:
            time.sleep(delay)  # be polite to UNC's server
        try:
            sections = {s.section: s for s in fetch(term, subject, catalog)}
        except Exception:
            log.exception("Failed to fetch %s %s %s", term, subject, catalog)
            continue
        for w in group:
            sec = sections.get(w.section)
            if sec is None:
                continue
            was_full = w.last_seats is None or w.last_seats <= 0
            if was_full and sec.available_seats > 0:
                try:
                    notify(w, sec)
                except Exception:
                    log.exception("Failed to send alert for watch %d", w.id)
                    continue
                w.notified_at = utcnow()
                sent += 1
            w.last_seats = sec.available_seats
    session.commit()
    return sent


def run_check_once() -> int:
    """One full check with its own database session (used by both runners)."""
    with SessionLocal() as session:
        return check_watches(session, delay=config.CHECK_REQUEST_DELAY_SECONDS)
