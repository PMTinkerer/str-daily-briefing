"""Tests for src/parsers/guesty.py.

Requires tests/sample_data/guesty_sample.html to exist.
Run first: python scripts/fetch_guesty_sample.py
"""

import os
import re

import pytest

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "sample_data", "guesty_sample.html")

if not os.path.exists(SAMPLE_PATH):
    pytest.skip(
        "guesty_sample.html not found — run: python scripts/fetch_guesty_sample.py",
        allow_module_level=True,
    )

from src.parsers.guesty import parse_guesty_report

EXPECTED_KEYS = {
    "check_in",
    "check_out",
    "listing_name",
    "listing_full",
    "city",
    "creation_date",
    "platform",
    "commission",
    "total_payout",
    "accommodation_fare",
    "source",
    "channel_reservation_id",
}

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def reservations() -> list[dict]:
    with open(SAMPLE_PATH, encoding="utf-8") as f:
        html = f.read()
    return parse_guesty_report(html)


def test_returns_nonempty_list(reservations: list[dict]) -> None:
    assert isinstance(reservations, list)
    assert len(reservations) > 0, "Expected at least one reservation"


def test_all_keys_present(reservations: list[dict]) -> None:
    for i, r in enumerate(reservations):
        assert set(r.keys()) == EXPECTED_KEYS, f"Row {i} missing keys: {EXPECTED_KEYS - set(r.keys())}"


def test_commission_is_float(reservations: list[dict]) -> None:
    for i, r in enumerate(reservations):
        assert isinstance(r["commission"], float), f"Row {i}: commission is {type(r['commission'])}"


def test_dates_are_iso_format(reservations: list[dict]) -> None:
    """Each date value must be either a valid YYYY-MM-DD string or an empty string."""
    date_fields = ("check_in", "check_out", "creation_date")
    for i, r in enumerate(reservations):
        for field in date_fields:
            value = r[field]
            assert value == "" or ISO_DATE_RE.match(value), (
                f"Row {i}: {field}={value!r} is neither empty nor YYYY-MM-DD"
            )


def test_check_out_mostly_valid(reservations: list[dict]) -> None:
    """At least 90% of check_out values must be valid dates — catches systemic failures."""
    valid = sum(1 for r in reservations if ISO_DATE_RE.match(r["check_out"]))
    pct = valid / len(reservations)
    assert pct >= 0.9, (
        f"Only {valid}/{len(reservations)} ({pct:.0%}) check_out values are valid dates"
    )


def test_listing_name_no_slash(reservations: list[dict]) -> None:
    for i, r in enumerate(reservations):
        assert " / " not in r["listing_name"], (
            f"Row {i}: listing_name={r['listing_name']!r} still contains ' / '"
        )


def test_sorted_by_check_in(reservations: list[dict]) -> None:
    dates = [r["check_in"] for r in reservations]
    assert dates == sorted(dates), "Reservations are not sorted by check_in date"
