# UNC Seat Alert

Get an email the moment a seat opens in a full UNC Chapel Hill class.

Pick the sections you want, confirm your email, and a background worker checks UNC's
public [class search](https://reports.unc.edu/class-search/) every couple of minutes.
When a full section opens up, you get an email with a link to register.

## How it works

```
 user ──► POST /api/watches ──► check section exists on UNC ──► save watch
                                        │
                                        └─► new user? send confirmation email
                                                                   │
 user clicks link ──► GET /api/verify ──► subscriber verified ◄────┘

 checker worker (every 2 min)
   │  loads watches for verified users only
   │  groups by course, so each course page is fetched once
   ▼
 reports.unc.edu ──► parse seats ──► full → open? ──► email alert (+ unsubscribe link)
```

| File | What it does |
|---|---|
| `app/scraper.py` | Fetches and parses the class search results table |
| `app/checker.py` | Alerts only on full → open transitions; retries alerts that failed to send |
| `app/main.py` | REST API: look up sections, sign up, verify, manage watches |
| `app/mailer.py` | Sends email over SMTP, or prints it to the console in local mode |
| `app/ratelimit.py` | Sliding-window rate limiter for the sign-up endpoint |
| `app/db.py` | `Subscriber` and `Watch` tables (SQLAlchemy 2.0) |

## Security and abuse protection

- **Email verification.** Nobody gets alerts until they click the link sent to their inbox,
  so you can't sign someone else up.
- **Secret tokens.** Viewing or deleting watches needs a random token that's only ever sent
  by email, so knowing someone's address isn't enough.
- **Rate limits.** Sign-ups are limited per IP, confirmation emails can be resent at most once
  per 5 minutes per address, and each person can watch up to 10 sections.
- **Polite scraping.** One request per course per check (no matter how many people watch it),
  with a pause between requests.

## Run locally

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # optional: add SMTP settings to send real email

uvicorn app.main:app --reload      # API at http://localhost:8000/docs
python -m app.run_checker          # in a second terminal
pytest                             # run tests
```

Without SMTP settings, emails (including confirmation links) are printed in the server log.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/sections?term=2027 Spring&subject=COMP&catalog_number=211` | Live seat counts for a course |
| POST | `/api/watches` | Watch a section (`email`, `term`, `subject`, `catalog_number`, `section`) |
| GET | `/api/verify?token=...` | Confirm email (link from the confirmation email) |
| GET | `/api/watches?token=...` | List your watches |
| DELETE | `/api/watches/{id}?token=...` | Stop watching |
| GET | `/api/unsubscribe/{id}?token=...` | One-click unsubscribe link from alert emails |

## Roadmap

- [x] Week 1: scraper, database, API, checker, tests
- [x] Week 2: email alerts, email verification, secure tokens, rate limiting
- [ ] Week 3: frontend, Docker, Postgres, deploy, GitHub Actions CI
- [ ] Week 4: launch to students, usage metrics, demo GIF
