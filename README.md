# UNC Seat Alert

[![CI](https://github.com/Tanuj-D/seat-alert/actions/workflows/ci.yml/badge.svg)](https://github.com/Tanuj-D/seat-alert/actions/workflows/ci.yml)

Get an email the moment a seat opens in a full UNC Chapel Hill class.

Search for a class, click **Watch** on a full section, and confirm your email. A background
worker checks UNC's public [class search](https://reports.unc.edu/class-search/) every couple
of minutes and emails you as soon as a seat opens.

**Stack:** Python 3.13 · FastAPI · SQLAlchemy 2.0 · PostgreSQL · Alembic · Docker · GitHub Actions

## How it works

```
 browser ──► GET /api/sections ──► (60s cache) ──► reports.unc.edu
    │
    └──► POST /api/watches ──► section exists? ──► save watch
                                                       │
                                     new user? ──► confirmation email ──► GET /api/verify

 checker (every 2 min)
   │  loads watches for verified users only
   │  groups by course, so each course page is fetched once
   ▼
 reports.unc.edu ──► parse seats ──► full → open? ──► email alert (+ unsubscribe link)
```

| File | What it does |
|---|---|
| `app/scraper.py` | Fetches and parses UNC's class search results and term list |
| `app/checker.py` | Alerts only on full → open transitions; retries alerts that failed to send |
| `app/main.py` | Web pages and REST API: search, sign up, verify, manage watches |
| `app/static/` | The sign-up and manage pages (plain HTML, CSS and JavaScript, no build step) |
| `app/mailer.py` | Sends email over SMTP, or prints it to the console in local mode |
| `app/ratelimit.py`, `app/cache.py` | Per-IP rate limiting and a short-lived cache for UNC lookups |
| `app/db.py`, `migrations/` | `Subscriber` and `Watch` tables, with Alembic migrations |

## Security and abuse protection

- **Email verification.** Nobody gets alerts until they click the link sent to their inbox,
  so you can't sign someone else up.
- **Secret tokens.** Viewing or deleting watches needs a random token that's only ever sent
  by email, so knowing someone's address isn't enough.
- **Rate limits.** Searches and sign-ups are limited per IP (the app reads the real client IP
  behind a load balancer). Confirmation emails can be resent at most once per 5 minutes per
  address, and each person can watch up to 10 sections.
- **Polite scraping.** One request per course per check no matter how many people watch it,
  a pause between requests, and a 60-second cache for searches from the web page.

## Run locally

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env               # optional: add SMTP settings to send real email

uvicorn app.main:app --reload      # open http://localhost:8000
python -m app.run_checker          # in a second terminal
pytest                             # run tests
```

Without SMTP settings, emails (including confirmation links) are printed in the server log.
Locally the app uses SQLite; the database is created and migrated automatically on startup.

### With Docker (PostgreSQL, like production)

```bash
docker compose up --build          # open http://localhost:8000
```

This starts PostgreSQL, the web app and the checker as separate containers.

## Changing the database

After editing the models in `app/db.py`, create a migration and commit it:

```bash
alembic revision --autogenerate -m "describe the change"
```

Migrations run automatically when the app starts. A test fails if the models and the
migrations ever drift apart.

## Deploy (Render)

1. In Render, choose **New → Blueprint** and pick this repository. `render.yaml` sets up the
   web service and a PostgreSQL database. Check the plans and prices it shows before applying.
2. Fill in the prompted settings: `BASE_URL` (your app's public URL) and the `SMTP_*` /
   `EMAIL_FROM` email settings.

The checker runs inside the web service (`EMBEDDED_CHECKER=true`), so one service is enough.
Use a plan that stays awake; on a free instance that sleeps when idle, the checker stops too.

## CI

Every push and pull request runs the tests against both SQLite and PostgreSQL, and checks
that the Docker image builds.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/options` | Terms and subject codes for the search form |
| GET | `/api/sections?term=2027 Spring&subject=COMP&catalog_number=211` | Live seat counts for a course |
| POST | `/api/watches` | Watch a section (`email`, `term`, `subject`, `catalog_number`, `section`) |
| GET | `/api/verify?token=...` | Confirm email (link from the confirmation email) |
| GET | `/api/watches?token=...` | List your watches |
| DELETE | `/api/watches/{id}?token=...` | Stop watching |
| GET | `/api/unsubscribe/{id}?token=...` | One-click unsubscribe link from alert emails |

Interactive docs are at `/docs` when the app is running.

## Roadmap

- [x] Scraper, database, API and seat checker
- [x] Email alerts, verification, secure tokens and rate limiting
- [x] Web pages, PostgreSQL + migrations, Docker, CI and deploy config
- [ ] Deploy and launch to students
- [ ] Usage metrics and a demo GIF
