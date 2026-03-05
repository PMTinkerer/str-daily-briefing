"""Parse Breezeway CSV attachment into a list of task dicts."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_VALID_TIERS = {"Luxe", "Mid", "Economy"}

# Breezeway date formats (try in order): M/DD/YY (e.g. "9/15/25") or YYYY-MM-DD
_DATE_FORMATS = ("%m/%d/%y", "%Y-%m-%d")


def parse_breezeway_report(csv_content: str) -> list[dict]:
    """Parse the CSV content of a Breezeway report attachment into a list of task dicts.

    Args:
        csv_content: Raw CSV string from the Breezeway email attachment.

    Returns:
        List of task dicts sorted by due_date, each with keys:
            task_title (str), property_name (str), property_address (str),
            property_tags (list[str]), city (str), tier (str),
            due_date (str, YYYY-MM-DD), status (str),
            estimated_time_minutes (int), created_date (str, YYYY-MM-DD),
            task_report_link (str).
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    tasks: list[dict] = []

    for row_num, row in enumerate(reader, start=2):
        if not any(v.strip() for v in row.values()):
            continue  # blank row

        try:
            task = _parse_row(row, row_num)
        except Exception:
            logger.warning("Failed to parse row %d, skipping", row_num, exc_info=True)
            continue

        tasks.append(task)

    tasks.sort(key=lambda t: t["due_date"])
    logger.info("Parsed %d task(s) from Breezeway report", len(tasks))
    return tasks


def _parse_row(row: dict, row_num: int) -> dict:
    """Parse a single CSV row into a task dict.

    Args:
        row: Dict of column name → raw string value from csv.DictReader.
        row_num: Row number for logging context.

    Returns:
        Task dict with all expected keys:
            task_title, property_name, property_address, property_tags, city, tier,
            due_date, status, estimated_time_minutes, created_date, task_report_link,
            department, priority, assignee, requested_by, created_by, last_updated_date.
    """
    raw_property = (row.get("Property") or "").strip()
    if " - " in raw_property:
        property_name, property_address = raw_property.split(" - ", 1)
    else:
        property_name, property_address = raw_property, ""

    tags, city, tier = _parse_tags(row.get("Property tags") or "")

    return {
        "task_title": (row.get("Task title") or "").strip(),
        "property_name": property_name.strip(),
        "property_address": property_address.strip(),
        "property_tags": tags,
        "city": city,
        "tier": tier,
        "due_date": _parse_date(row.get("Due date") or "", row_num, "due_date"),
        "status": (row.get("Status") or "").strip(),
        "estimated_time_minutes": _parse_estimated_time(row.get("Estimated time") or "", row_num),
        "created_date": _parse_date(row.get("Created date") or "", row_num, "created_date"),
        "task_report_link": (row.get("Task report link") or "").strip(),
        "department": (row.get("Department") or "").strip(),
        "priority": (row.get("Priority") or "").strip(),
        "assignee": (row.get("Assignees") or "").strip(),
        "requested_by": (row.get("Requested by") or "").strip(),
        "created_by": (row.get("Created by") or "").strip(),
        "last_updated_date": _parse_date(row.get("Last updated date") or "", row_num, "last_updated_date"),
    }


def _parse_tags(raw_tags: str) -> tuple[list[str], str, str]:
    """Parse the semicolon-separated property tags into components.

    Args:
        raw_tags: Raw tag string from the CSV (e.g. "Breezeway Cleaning; Luxe; Sandpiper - Main House; Ogunquit").

    Returns:
        Tuple of (tags, city, tier) where:
            tags is a list of stripped non-empty tag strings,
            city is the last tag (or empty string),
            tier is the first tag that matches Luxe/Mid/Economy (or empty string).
    """
    if not raw_tags.strip():
        return [], "", ""

    tags = [t.strip() for t in raw_tags.split(";") if t.strip()]
    city = tags[-1] if tags else ""
    tier = next((t for t in tags if t in _VALID_TIERS), "")
    return tags, city, tier


def _parse_date(value: str, row_num: int, field: str) -> str:
    """Parse a Breezeway date string into YYYY-MM-DD format.

    Args:
        value: Raw date string (e.g. "9/15/25" or "2026-03-05").
        row_num: Row number for logging context.
        field: Field name for logging context.

    Returns:
        Date string in YYYY-MM-DD format, or raw value if parsing fails.
    """
    if not value:
        return value
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.warning("Row %d: could not parse date for '%s': %r", row_num, field, value)
    return value


def _parse_estimated_time(value: str, row_num: int) -> int:
    """Parse an HH:MM:SS duration string into total minutes.

    Args:
        value: Duration string (e.g. "1:00:00", "0:45:00") or empty string.
        row_num: Row number for logging context.

    Returns:
        Total minutes as an integer. Returns 0 for empty or unparseable values.
    """
    if not value.strip():
        return 0
    try:
        parts = value.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        logger.warning("Row %d: could not parse estimated_time: %r", row_num, value)
        return 0
