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
