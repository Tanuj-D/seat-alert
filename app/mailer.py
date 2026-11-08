"""Sending email. Uses SMTP when configured, otherwise logs emails to the console."""

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from app import config

log = logging.getLogger(__name__)


@dataclass
class Email:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, email: Email) -> None: ...


@dataclass
class ConsoleMailer:
    """Logs emails instead of sending them. Keeps a copy in `sent` (handy in tests)."""

    sent: list[Email] = field(default_factory=list)

    def send(self, email: Email) -> None:
        self.sent.append(email)
        log.info("EMAIL to=%s subject=%r\n%s", email.to, email.subject, email.body)


class SMTPMailer:
    """Works with Gmail (app password), Resend, Mailgun, SendGrid, etc."""

    def send(self, email: Email) -> None:
        msg = EmailMessage()
        msg["From"] = config.EMAIL_FROM
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.body)
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)


def build_mailer() -> Mailer:
    return SMTPMailer() if config.SMTP_HOST else ConsoleMailer()


# Other modules call `mailer.mailer.send(...)` so tests can swap this out.
mailer: Mailer = build_mailer()


# --- Email templates ---------------------------------------------------------

def verification_email(to: str, token: str) -> Email:
    link = f"{config.BASE_URL}/api/verify?token={token}"
    return Email(
        to=to,
        subject="Confirm your UNC Seat Alert email",
        body=(
            "Click the link below to confirm your email and start getting seat alerts:\n\n"
            f"{link}\n\n"
            "Keep this email: you can see and manage your watched classes any time here:\n"
            f"{config.BASE_URL}/manage?token={token}\n\n"
            "If you didn't sign up, ignore this email and you won't hear from us again."
        ),
    )


def seat_alert_email(to: str, course: str, title: str, schedule: str,
                     seats: int, unsubscribe_link: str, manage_link: str) -> Email:
    plural = "seat is" if seats == 1 else "seats are"
    return Email(
        to=to,
        subject=f"Seat open: {course}",
        body=(
            f"Good news! {seats} {plural} open in {course} ({title}, {schedule}).\n\n"
            "Seats go fast, so register now in ConnectCarolina:\n"
            "https://connectcarolina.unc.edu\n\n"
            f"Stop watching this section: {unsubscribe_link}\n"
            f"Manage all your watched classes: {manage_link}"
        ),
    )
