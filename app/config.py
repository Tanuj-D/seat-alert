"""App settings, read from environment variables (and a local .env file if present)."""

import os

from dotenv import load_dotenv

load_dotenv()  # never overrides variables already set in the environment

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./seat_alert.db")
# Public URL of the app, used to build links in emails.
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

# Email. If SMTP_HOST is empty, emails are printed to the log instead of sent.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "UNC Seat Alert <alerts@localhost>")

# Limits
MAX_WATCHES_PER_USER = int(os.getenv("MAX_WATCHES_PER_USER", "10"))
VERIFY_EMAIL_COOLDOWN_SECONDS = int(os.getenv("VERIFY_EMAIL_COOLDOWN_SECONDS", "300"))
CREATE_WATCH_LIMIT_PER_MINUTE = int(os.getenv("CREATE_WATCH_LIMIT_PER_MINUTE", "10"))

# Checker
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "120"))
# Pause between requests to UNC so we don't hammer their server.
CHECK_REQUEST_DELAY_SECONDS = float(os.getenv("CHECK_REQUEST_DELAY_SECONDS", "1.0"))
