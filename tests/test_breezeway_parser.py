"""Tests for src/parsers/breezeway.py.

Requires tests/sample_data/breezeway_sample.csv to exist.
Run first: python3 scripts/fetch_breezeway_sample.py
"""

import os
import re

import pytest

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "sample_data", "breezeway_sample.csv")

if not os.path.exists(SAMPLE_PATH):
    pytest.skip(
        "breezeway_sample.csv not found — run: python3 scripts/fetch_breezeway_sample.py",
        allow_module_level=True,
    )

from src.parsers.breezeway import parse_breezeway_report

EXPECTED_KEYS = {
    "task_title",
    "property_name",
    "property_address",
    "property_tags",
    "city",
    "tier",
    "due_date",
    "status",
    "estimated_time_minutes",
    "created_date",
    "task_report_link",
    "department",
    "priority",
    "assignee",
    "requested_by",
    "created_by",
    "last_updated_date",
}

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_TIERS = {"Luxe", "Mid", "Economy", ""}


@pytest.fixture(scope="module")
def tasks() -> list[dict]:
    with open(SAMPLE_PATH, encoding="utf-8") as f:
        csv_content = f.read()
    return parse_breezeway_report(csv_content)


def test_returns_nonempty_list(tasks: list[dict]) -> None:
    assert isinstance(tasks, list)
    assert len(tasks) > 0, "Expected at least one task"


def test_all_keys_present(tasks: list[dict]) -> None:
    for i, t in enumerate(tasks):
        assert set(t.keys()) == EXPECTED_KEYS, f"Row {i} missing keys: {EXPECTED_KEYS - set(t.keys())}"


def test_due_dates_are_iso_format(tasks: list[dict]) -> None:
    for i, t in enumerate(tasks):
        value = t["due_date"]
        assert value == "" or ISO_DATE_RE.match(value), (
            f"Row {i}: due_date={value!r} is neither empty nor YYYY-MM-DD"
        )


def test_property_tags_is_list(tasks: list[dict]) -> None:
    for i, t in enumerate(tasks):
        assert isinstance(t["property_tags"], list), (
            f"Row {i}: property_tags is {type(t['property_tags'])}, expected list"
        )


def test_city_is_string(tasks: list[dict]) -> None:
    for i, t in enumerate(tasks):
        assert isinstance(t["city"], str), f"Row {i}: city is {type(t['city'])}"
        # Rows with tags should have a non-empty city
        if t["property_tags"]:
            assert t["city"], f"Row {i}: has tags but city is empty"


def test_tier_is_valid(tasks: list[dict]) -> None:
    for i, t in enumerate(tasks):
        assert t["tier"] in VALID_TIERS, (
            f"Row {i}: tier={t['tier']!r} is not one of {VALID_TIERS}"
        )


def test_estimated_time_is_int(tasks: list[dict]) -> None:
    for i, t in enumerate(tasks):
        assert isinstance(t["estimated_time_minutes"], int), (
            f"Row {i}: estimated_time_minutes is {type(t['estimated_time_minutes'])}"
        )


def test_sorted_by_due_date(tasks: list[dict]) -> None:
    dates = [t["due_date"] for t in tasks]
    assert dates == sorted(dates), "Tasks are not sorted by due_date"


def test_new_fields_are_strings(tasks: list[dict]) -> None:
    for i, t in enumerate(tasks):
        for field in ("department", "priority", "assignee", "requested_by", "created_by"):
            assert isinstance(t[field], str), f"Row {i}: {field} is not str"


def test_last_updated_date_is_iso_or_empty(tasks: list[dict]) -> None:
    for i, t in enumerate(tasks):
        val = t["last_updated_date"]
        assert val == "" or ISO_DATE_RE.match(val), (
            f"Row {i}: last_updated_date={val!r} is not YYYY-MM-DD or empty"
        )


def test_backward_compat_old_csv() -> None:
    """Old CSV without new columns should parse without error; new fields default to empty."""
    old_csv = (
        "Task title,Property,Property tags,Due date,Status,Estimated time,"
        "Created date,Task report link,Property Time Zone\n"
        '"Arrival Inspection - L","Sandpiper - 18 School St",'
        '"Breezeway Cleaning; Luxe; Sandpiper; Ogunquit",'
        '"9/15/25","Created","1:00:00","7/31/25",'
        '"https://portal.breezeway.io/task/report/abc",'
        '"(UTC-05:00) Eastern Time (US & Canada)"\n'
    )
    result = parse_breezeway_report(old_csv)
    assert len(result) == 1
    t = result[0]
    for field in ("department", "priority", "assignee", "requested_by", "created_by", "last_updated_date"):
        assert t[field] == "", f"Expected empty string for {field} on old CSV, got {t[field]!r}"
