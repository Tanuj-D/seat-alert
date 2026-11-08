"""Check every watched section and send alerts when seats open up."""

import logging
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Watch, utcnow
from app.scraper import Section, fetch_sections

log = logging.getLogger(__name__)

Fetcher = Callable[[str, str, str], list[Section]]
Notifier = Callable[[Watch, Section], None]


def log_notifier(watch: Watch, section: Section) -> None:
    # Placeholder until email is added in week 2.
    log.info("ALERT %s: %s %s-%s has %d seats",
             watch.email, section.subject, section.catalog_number,
             section.section, section.available_seats)


def check_watches(session: Session, fetch: Fetcher = fetch_sections,
                  notify: Notifier = log_notifier) -> int:
    """Run one pass over all watches. Returns how many alerts were sent.

    Watches are grouped by course so each course page is fetched once, no
    matter how many people watch it. An alert fires only when a section goes
    from 0 seats (or unknown) to at least 1, so users aren't spammed every run.
    """
    groups: dict[tuple[str, str, str], list[Watch]] = defaultdict(list)
    for w in session.scalars(select(Watch)):
        groups[(w.term, w.subject, w.catalog_number)].append(w)

    sent = 0
    for (term, subject, catalog), watches in groups.items():
        try:
            sections = {s.section: s for s in fetch(term, subject, catalog)}
        except Exception:
            log.exception("Failed to fetch %s %s %s", term, subject, catalog)
            continue
        for w in watches:
            sec = sections.get(w.section)
            if sec is None:
                continue
            was_full = w.last_seats is None or w.last_seats <= 0
            if was_full and sec.available_seats > 0:
                notify(w, sec)
                w.notified_at = utcnow()
                sent += 1
            w.last_seats = sec.available_seats
    session.commit()
    return sent
