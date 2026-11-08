from fastapi.testclient import TestClient

from app import config, scraper
from app.main import app

client = TestClient(app)


def test_home_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "UNC Seat Alert" in resp.text


def test_manage_page():
    assert client.get("/manage?token=x").status_code == 200


def test_static_css():
    assert client.get("/static/app.css").status_code == 200


def test_terms_endpoint_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(scraper, "fetch_terms", lambda: calls.append(1) or ["2027 Spring"])
    assert client.get("/api/terms").json() == ["2027 Spring"]
    client.get("/api/terms")
    assert len(calls) == 1


def test_section_searches_are_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(scraper, "fetch_sections", lambda *a: calls.append(a) or [])
    for subject in ("comp", "COMP", " COMP "):
        client.get("/api/sections",
                   params={"term": "2027 Spring", "subject": subject, "catalog_number": "211"})
    assert calls == [("2027 Spring", "COMP", "211")]


def test_search_rate_limit(monkeypatch):
    monkeypatch.setattr(scraper, "fetch_sections", lambda *a: [])
    codes = [client.get("/api/sections", params={"term": "t", "subject": "COMP",
                                                 "catalog_number": str(i)}).status_code
             for i in range(config.SEARCH_LIMIT_PER_MINUTE + 1)]
    assert codes[-1] == 429 and codes[0] == 200


def test_verify_page_links_to_manage(outbox):
    client.post("/api/watches", json={"email": "a@unc.edu", "term": "2027 Spring",
                                      "subject": "COMP", "catalog_number": "211",
                                      "section": "001"})
    body = outbox[-1].body
    token = body.split("verify?token=")[1].split()[0]
    assert f"/manage?token={token}" in body
    page = client.get("/api/verify", params={"token": token})
    assert f"/manage?token={token}" in page.text


def test_postgres_urls_are_normalized():
    assert config._normalize_db_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert config._normalize_db_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert config._normalize_db_url("sqlite:///x.db") == "sqlite:///x.db"
