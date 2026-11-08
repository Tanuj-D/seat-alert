from app.checker import check_watches
from app.db import Subscriber, Watch
from app.scraper import Section


def make_section(seats: int, section: str = "001") -> Section:
    return Section("COMP", "211", section, "4696", "System Programming", "2027 Spring",
                   "MWF 11:15 AM-12:05 PM", "In-Person", seats)


def add_watch(session, sub: Subscriber, section="001"):
    w = Watch(subscriber_id=sub.id, term="2027 Spring", subject="COMP",
              catalog_number="211", section=section)
    session.add(w)
    session.commit()
    return w


def run(session, seats_by_call):
    """Run the checker once per entry, returning the list of alerts sent."""
    alerts = []
    for seats in seats_by_call:
        check_watches(session,
                      fetch=lambda *_: [make_section(seats)],
                      notify=lambda w, s: alerts.append((w.subscriber.email, s.available_seats)))
    return alerts


def test_alerts_when_seat_opens(session, verified_subscriber):
    add_watch(session, verified_subscriber)
    assert run(session, [0, 3]) == [("a@unc.edu", 3)]


def test_no_repeat_alert_while_seats_stay_open(session, verified_subscriber):
    add_watch(session, verified_subscriber)
    assert len(run(session, [0, 3, 2, 5])) == 1


def test_alerts_again_after_class_refills(session, verified_subscriber):
    add_watch(session, verified_subscriber)
    assert len(run(session, [0, 1, 0, 1])) == 2


def test_unverified_subscribers_get_no_alerts(session):
    sub = Subscriber(email="new@unc.edu")
    session.add(sub)
    session.commit()
    add_watch(session, sub)
    assert run(session, [0, 3]) == []


def test_fetches_each_course_once(session, verified_subscriber):
    other = Subscriber(email="b@unc.edu", verified_at=verified_subscriber.verified_at)
    session.add(other)
    session.commit()
    add_watch(session, verified_subscriber)
    add_watch(session, other)
    calls = []

    def fetch(*args):
        calls.append(args)
        return [make_section(5)]

    sent = check_watches(session, fetch=fetch, notify=lambda *_: None)
    assert sent == 2
    assert len(calls) == 1


def test_fetch_failure_does_not_crash(session, verified_subscriber):
    add_watch(session, verified_subscriber)

    def broken(*_):
        raise RuntimeError("site down")

    assert check_watches(session, fetch=broken, notify=lambda *_: None) == 0


def test_failed_alert_is_retried_next_run(session, verified_subscriber):
    add_watch(session, verified_subscriber)
    attempts = []

    def flaky(w, s):
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("SMTP down")

    for _ in range(2):
        check_watches(session, fetch=lambda *_: [make_section(3)], notify=flaky)
    assert len(attempts) == 2


def test_default_notifier_sends_email(session, verified_subscriber, outbox):
    w = add_watch(session, verified_subscriber)
    check_watches(session, fetch=lambda *_: [make_section(2)])

    assert len(outbox) == 1
    email = outbox[0]
    assert email.to == "a@unc.edu"
    assert email.subject == "Seat open: COMP 211-001"
    assert "2 seats are open" in email.body
    assert f"/api/unsubscribe/{w.id}?token={verified_subscriber.token}" in email.body
