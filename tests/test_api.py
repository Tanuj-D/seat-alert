import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, scraper
from app.db import Subscriber
from app.main import app

client = TestClient(app)
WATCH = {"email": "A@unc.edu", "term": "2027 Spring", "subject": "comp",
         "catalog_number": "211", "section": "001"}


def token_from(outbox) -> str:
    return re.search(r"token=([\w-]+)", outbox[-1].body).group(1)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_sections_endpoint():
    resp = client.get("/api/sections",
                      params={"term": "2027 Spring", "subject": "COMP", "catalog_number": "211"})
    assert resp.status_code == 200
    assert [s["available_seats"] for s in resp.json()] == [0, 40]


# --- Sign-up and verification -------------------------------------------------

def test_new_user_gets_verification_email(outbox):
    resp = client.post("/api/watches", json=WATCH)
    assert resp.status_code == 201
    body = resp.json()
    assert body["verified"] is False
    assert body["watch"]["subject"] == "COMP"
    assert body["watch"]["last_seats"] == 0  # starts from the current seat count

    assert len(outbox) == 1
    assert outbox[0].to == "a@unc.edu"  # emails are normalized to lowercase
    assert "/api/verify?token=" in outbox[0].body


def test_verify_link_confirms_email(outbox, session):
    client.post("/api/watches", json=WATCH)
    resp = client.get("/api/verify", params={"token": token_from(outbox)})
    assert resp.status_code == 200
    assert "Email confirmed" in resp.text
    assert session.query(Subscriber).one().verified


def test_bad_verify_link():
    resp = client.get("/api/verify", params={"token": "nope"})
    assert resp.status_code == 404


def test_verification_email_not_resent_within_cooldown(outbox):
    client.post("/api/watches", json=WATCH)
    client.post("/api/watches", json=WATCH | {"section": "002"})
    assert len(outbox) == 1


def test_verified_user_gets_no_extra_email(outbox):
    client.post("/api/watches", json=WATCH)
    client.get("/api/verify", params={"token": token_from(outbox)})
    resp = client.post("/api/watches", json=WATCH | {"section": "002"})
    assert resp.json()["verified"] is True
    assert len(outbox) == 1


# --- Validation -------------------------------------------------------------

def test_unknown_section_rejected():
    resp = client.post("/api/watches", json=WATCH | {"section": "999"})
    assert resp.status_code == 404


def test_saves_full_term_from_unc():
    resp = client.post("/api/watches", json=WATCH | {"term": "Spring"})
    assert resp.json()["watch"]["term"] == "2027 Spring"


def test_unc_down_returns_502(monkeypatch):
    def down(*_):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(scraper, "fetch_sections", down)
    assert client.post("/api/watches", json=WATCH).status_code == 502


def test_duplicate_watch_rejected():
    assert client.post("/api/watches", json=WATCH).status_code == 201
    assert client.post("/api/watches", json=WATCH).status_code == 409


def test_invalid_email_rejected():
    assert client.post("/api/watches", json=WATCH | {"email": "nope"}).status_code == 422


def test_watch_limit_per_user(monkeypatch):
    monkeypatch.setattr(config, "MAX_WATCHES_PER_USER", 1)
    assert client.post("/api/watches", json=WATCH).status_code == 201
    assert client.post("/api/watches", json=WATCH | {"section": "002"}).status_code == 400


def test_rate_limit_per_ip():
    statuses = [client.post("/api/watches", json=WATCH | {"email": f"u{i}@unc.edu"}).status_code
                for i in range(config.CREATE_WATCH_LIMIT_PER_MINUTE + 1)]
    assert statuses[:-1] == [201] * config.CREATE_WATCH_LIMIT_PER_MINUTE
    assert statuses[-1] == 429


# --- Managing watches requires the secret token ------------------------------

@pytest.fixture
def signed_up(outbox):
    watch_id = client.post("/api/watches", json=WATCH).json()["watch"]["id"]
    return watch_id, token_from(outbox)


def test_list_and_delete_with_token(signed_up):
    watch_id, token = signed_up
    assert len(client.get("/api/watches", params={"token": token}).json()) == 1
    assert client.delete(f"/api/watches/{watch_id}", params={"token": token}).status_code == 204
    assert client.get("/api/watches", params={"token": token}).json() == []


def test_wrong_token_cannot_list_or_delete(signed_up):
    watch_id, _ = signed_up
    assert client.get("/api/watches", params={"token": "guess"}).status_code == 404
    assert client.delete(f"/api/watches/{watch_id}", params={"token": "guess"}).status_code == 404


def test_other_users_token_cannot_delete(signed_up, outbox):
    watch_id, _ = signed_up
    client.post("/api/watches", json=WATCH | {"email": "b@unc.edu"})
    other_token = token_from(outbox)
    resp = client.delete(f"/api/watches/{watch_id}", params={"token": other_token})
    assert resp.status_code == 404


def test_unsubscribe_link(signed_up):
    watch_id, token = signed_up
    resp = client.get(f"/api/unsubscribe/{watch_id}", params={"token": token})
    assert "no longer get alerts for COMP 211-001" in resp.text
    assert client.get("/api/watches", params={"token": token}).json() == []
    # Clicking it twice is harmless.
    again = client.get(f"/api/unsubscribe/{watch_id}", params={"token": token})
    assert again.status_code == 200
