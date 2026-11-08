from app.checker import check_watches
from app.db import Watch
from app.scraper import Section


def make_section(seats: int, section: str = "001") -> Section:
    return Section("COMP", "211", section, "4696", "System Programming", "2027 Spring",
                   "MWF 11:15 AM-12:05 PM", "In-Person", seats)


def add_watch(session, email="a@unc.edu", section="001"):
    session.add(Watch(email=email, term="2027 Spring", subject="COMP",
                      catalog_number="211", section=section))
    session.commit()


def run(session, seats_by_call):
    """Run the checker once per entry, returning the list of alerts sent."""
    alerts = []
    for seats in seats_by_call:
        check_watches(session,
                      fetch=lambda *_: [make_section(seats)],
                      notify=lambda w, s: alerts.append((w.email, s.available_seats)))
    return alerts


def test_alerts_when_seat_opens(session):
    add_watch(session)
    assert run(session, [0, 3]) == [("a@unc.edu", 3)]


def test_no_repeat_alert_while_seats_stay_open(session):
    add_watch(session)
    assert len(run(session, [0, 3, 2, 5])) == 1


def test_alerts_again_after_class_refills(session):
    add_watch(session)
    assert len(run(session, [0, 1, 0, 1])) == 2


def test_fetches_each_course_once(session):
    add_watch(session, email="a@unc.edu")
    add_watch(session, email="b@unc.edu")
    calls = []

    def fetch(*args):
        calls.append(args)
        return [make_section(5)]

    sent = check_watches(session, fetch=fetch, notify=lambda *_: None)
    assert sent == 2
    assert len(calls) == 1


def test_fetch_failure_does_not_crash(session):
    add_watch(session)

    def broken(*_):
        raise RuntimeError("site down")

    assert check_watches(session, fetch=broken, notify=lambda *_: None) == 0
