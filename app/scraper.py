"""Fetch and parse section data from UNC's public class search (reports.unc.edu)."""

import json
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

SEARCH_URL = "https://reports.unc.edu/class-search/"
USER_AGENT = "seat-alert/0.1 (student project)"


@dataclass(frozen=True)
class Section:
    subject: str
    catalog_number: str
    section: str
    class_number: str
    title: str
    term: str
    schedule: str
    instruction_mode: str
    available_seats: int


def parse_sections(html: str) -> list[Section]:
    """Turn a class search results page into Section objects.

    The table uses rowspan for subject and catalog number, so only the first
    row of each course has those cells. The last 10 cells of every row are
    always the per-section columns, so we read from the end and carry the
    subject and catalog number forward.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="results-table")
    if table is None:
        return []

    sections: list[Section] = []
    subject = catalog = ""
    for row in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 10:
            continue  # header row or something unexpected
        if len(cells) >= 12:
            subject, catalog = cells[-12], cells[-11]
        (_same_as, section, class_number, title, term, _hours,
         _dates, schedule, mode, seats) = cells[-10:]
        sections.append(Section(
            subject=subject,
            catalog_number=catalog,
            section=section,
            class_number=class_number,
            title=title,
            term=term,
            schedule=schedule,
            instruction_mode=mode,
            available_seats=int(seats) if seats.lstrip("-").isdigit() else 0,
        ))
    return sections


def parse_terms(html: str) -> list[str]:
    """Terms currently offered, e.g. ["2026 Fall", "2027 Spring"]."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="json_terms")
    if tag is None or not tag.string:
        return []
    terms = json.loads(tag.string)
    return [t for t in terms if isinstance(t, str)]


def fetch_terms() -> list[str]:
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15) as client:
        resp = client.get(SEARCH_URL, follow_redirects=True)
        resp.raise_for_status()
        return parse_terms(resp.text)


def fetch_sections(term: str, subject: str, catalog_number: str,
                   client: httpx.Client | None = None) -> list[Section]:
    """Look up every section of one course, e.g. ("2027 Spring", "COMP", "211")."""
    params = {"term": term, "subject": subject.upper(), "catalog_number": catalog_number}
    own_client = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15)
    try:
        resp = client.get(SEARCH_URL, params=params, follow_redirects=True)
        resp.raise_for_status()
        return parse_sections(resp.text)
    finally:
        if own_client:
            client.close()
