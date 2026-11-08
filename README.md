# UNC Seat Alert

Get notified the moment a seat opens in a full UNC Chapel Hill class.

Pick the sections you want, and a background worker checks UNC's public
[class search](https://reports.unc.edu/class-search/) every couple of minutes. When a full
section opens up, you get an alert.

## How it works

```
 user ──► FastAPI (/api/watches) ──► database (watches)
                                          ▲
 checker worker (every 2 min) ────────────┘
   │  groups watches by course, so each course is fetched once
   ▼
 reports.unc.edu class search ──► parse seats ──► full → open? ──► send alert
```

- **`app/scraper.py`**: fetches and parses the class search results table
- **`app/checker.py`**: alerts only when a section goes from full to open, so nobody gets spammed
- **`app/main.py`**: REST API for looking up sections and managing watches
- **`app/run_checker.py`**: the background worker loop

## Run locally

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload      # API at http://localhost:8000/docs
python -m app.run_checker          # in a second terminal
pytest                             # run tests
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/sections?term=2027 Spring&subject=COMP&catalog_number=211` | Live seat counts for a course |
| POST | `/api/watches` | Watch a section (`email`, `term`, `subject`, `catalog_number`, `section`) |
| GET | `/api/watches?email=...` | List your watches |
| DELETE | `/api/watches/{id}?email=...` | Stop watching |

## Roadmap

- [x] Week 1: scraper, database, API, checker, tests
- [ ] Week 2: real email alerts, email verification, rate limiting
- [ ] Week 3: frontend, Docker, Postgres, deploy, GitHub Actions CI
- [ ] Week 4: launch to students, usage metrics, demo GIF
