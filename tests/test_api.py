from fastapi.testclient import TestClient

from app import scraper
from app.main import app
from app.scraper import parse_sections

client = TestClient(app)
WATCH = {"email": "a@unc.edu", "term": "2027 Spring", "subject": "comp",
         "catalog_number": "211", "section": "001"}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_sections_endpoint(monkeypatch, comp211_html):
    monkeypatch.setattr(scraper, "fetch_sections", lambda *_: parse_sections(comp211_html))
    resp = client.get("/api/sections",
                      params={"term": "2027 Spring", "subject": "COMP", "catalog_number": "211"})
    assert resp.status_code == 200
    assert [s["available_seats"] for s in resp.json()] == [0, 40]


def test_create_list_delete_watch():
    created = client.post("/api/watches", json=WATCH)
    assert created.status_code == 201
    assert created.json()["subject"] == "COMP"

    listed = client.get("/api/watches", params={"email": "a@unc.edu"}).json()
    assert len(listed) == 1

    watch_id = created.json()["id"]
    # Someone else can't delete it.
    assert client.delete(f"/api/watches/{watch_id}", params={"email": "x@unc.edu"}).status_code == 404
    assert client.delete(f"/api/watches/{watch_id}", params={"email": "a@unc.edu"}).status_code == 204
    assert client.get("/api/watches", params={"email": "a@unc.edu"}).json() == []


def test_duplicate_watch_rejected():
    assert client.post("/api/watches", json=WATCH).status_code == 201
    assert client.post("/api/watches", json=WATCH).status_code == 409


def test_invalid_email_rejected():
    assert client.post("/api/watches", json=WATCH | {"email": "nope"}).status_code == 422
