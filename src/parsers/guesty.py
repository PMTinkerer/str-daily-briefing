"""Parse Guesty HTML email body into a list of reservation dicts."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Expected column header names (normalized to uppercase for matching)
_COLUMN_MAP = {
    "CHECK-IN": "check_in",
    "CHECK-OUT": "check_out",
    "LISTING": "listing",
    "LISTING'S CITY": "city",
    "CREATION DATE": "creation_date",
    "PLATFORM": "platform",
    "COMMISSION": "commission",
}

_REQUIRED_KEYS = {"check_in", "check_out", "listing", "city", "creation_date", "platform", "commission"}

# Guesty date format per CLAUDE.md: "YYYY-MM-DD HH:MM AM/PM"
_DATE_FORMAT = "%Y-%m-%d %I:%M %p"


def parse_guesty_report(html_body: str) -> list[dict]:
    """Parse the HTML body of a Guesty report email into a list of reservation dicts.

    Args:
        html_body: Raw HTML string from the Guesty report email body.

    Returns:
        List of reservation dicts sorted by check_in date, each with keys:
            check_in (str, YYYY-MM-DD), check_out (str, YYYY-MM-DD),
            listing_name (str), listing_full (str), city (str),
            creation_date (str, YYYY-MM-DD), platform (str), commission (float).
    """
    soup = BeautifulSoup(html_body, "lxml")
    table = soup.find("table")

    if table is None:
        logger.warning("No <table> found in Guesty email body")
        return []

    rows = table.find_all("tr")
    if not rows:
        logger.warning("Table has no rows")
        return []

    # Detect column indices from header row
    header_cells = [td.get_text(strip=True).upper() for td in rows[0].find_all(["th", "td"])]
    col_index: dict[str, int] = {}
    for i, cell_text in enumerate(header_cells):
        if cell_text in _COLUMN_MAP:
            col_index[_COLUMN_MAP[cell_text]] = i

    missing = _REQUIRED_KEYS - set(col_index.keys())
    if missing:
        logger.warning("Guesty table missing expected columns: %s", missing)
        if not col_index:
            return []

    reservations: list[dict] = []
    for row_num, row in enumerate(rows[1:], start=2):
        cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]

        if not any(cells):
            continue  # blank row

        try:
            reservation = _parse_row(cells, col_index, row_num)
        except Exception:
            logger.warning("Failed to parse row %d, skipping", row_num, exc_info=True)
            continue

        if reservation is not None:
            reservations.append(reservation)

    reservations.sort(key=lambda r: r["check_in"])
    logger.info("Parsed %d reservation(s) from Guesty report", len(reservations))
    return reservations


def _parse_row(cells: list[str], col_index: dict[str, int], row_num: int) -> dict | None:
    """Parse a single table row into a reservation dict.

    Args:
        cells: List of cell text values for this row.
        col_index: Mapping from field name to column index.
        row_num: Row number (for logging).

    Returns:
        Reservation dict, or None if the row should be skipped.
    """
    def get(field: str) -> str:
        idx = col_index.get(field)
        if idx is None or idx >= len(cells):
            return ""
        return cells[idx]

    listing_full = get("listing")
    listing_name = listing_full.split(" / ")[0].strip() if " / " in listing_full else listing_full

    return {
        "check_in": _parse_date(get("check_in"), row_num, "check_in"),
        "check_out": _parse_date(get("check_out"), row_num, "check_out"),
        "listing_name": listing_name,
        "listing_full": listing_full,
        "city": get("city"),
        "creation_date": _parse_date(get("creation_date"), row_num, "creation_date"),
        "platform": get("platform"),
        "commission": _parse_commission(get("commission"), row_num),
    }


def _parse_date(value: str, row_num: int, field: str) -> str:
    """Parse a Guesty date string into YYYY-MM-DD format.

    Args:
        value: Raw date string from the table cell.
        row_num: Row number for logging context.
        field: Field name for logging context.

    Returns:
        Date string in YYYY-MM-DD format, or raw value if parsing fails.
    """
    if not value:
        return value
    try:
        return datetime.strptime(value, _DATE_FORMAT).strftime("%Y-%m-%d")
    except ValueError:
        # Try just the date portion if the time part is missing or different
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            logger.warning("Row %d: could not parse date for '%s': %r", row_num, field, value)
            return value


def _parse_commission(value: str, row_num: int) -> float:
    """Parse a commission value into a float.

    Args:
        value: Raw commission string (may contain $, commas, whitespace).
        row_num: Row number for logging context.

    Returns:
        Commission as a float. Returns 0.0 if empty or unparseable.
    """
    if not value:
        return 0.0
    cleaned = re.sub(r"[$,\s]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        logger.warning("Row %d: could not parse commission value: %r", row_num, value)
        return 0.0
