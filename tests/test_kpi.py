"""Unit tests for src/kpi.py using synthetic fixture data."""

from __future__ import annotations

import pytest
from src.kpi import compute_kpis

TEST_DATE = "2026-03-04"
YESTERDAY = "2026-03-03"


def _make_reservation(
    check_in: str,
    check_out: str,
    listing_name: str,
    city: str,
    creation_date: str,
    platform: str,
    commission: float,
) -> dict:
    return {
        "check_in": check_in,
        "check_out": check_out,
        "listing_name": listing_name,
        "listing_full": listing_name,
        "city": city,
        "creation_date": creation_date,
        "platform": platform,
        "commission": commission,
    }


def _make_task(
    due_date: str,
    task_title: str,
    status: str,
    estimated_time_minutes: int,
    city: str,
    property_name: str,
    *,
    department: str = "",
    priority: str = "",
    assignee: str = "",
    requested_by: str = "",
    last_updated_date: str = "",
) -> dict:
    return {
        "task_title": task_title,
        "property_name": property_name,
        "property_address": "",
        "property_tags": [],
        "city": city,
        "tier": "",
        "due_date": due_date,
        "status": status,
        "estimated_time_minutes": estimated_time_minutes,
        "created_date": TEST_DATE,
        "task_report_link": "",
        "department": department,
        "priority": priority,
        "assignee": assignee,
        "requested_by": requested_by,
        "created_by": "",
        "last_updated_date": last_updated_date,
    }


@pytest.fixture
def reservations() -> list[dict]:
    return [
        # R1: check-in today, created yesterday
        _make_reservation(TEST_DATE, "2026-03-05", "Beach House", "Ogunquit", YESTERDAY, "Airbnb", 500.0),
        # R2: check-out today → part of same-day turn with R3
        _make_reservation("2026-03-10", TEST_DATE, "Sea Cottage", "York", "2026-02-01", "VRBO", 300.0),
        # R3: check-in today, same listing as R2 → same-day turn
        _make_reservation(TEST_DATE, "2026-03-06", "Sea Cottage", "York", "2026-03-02", "Airbnb", 250.0),
        # R4: future stay, created yesterday
        _make_reservation("2026-03-10", "2026-03-15", "Farm Stay", "Kennebunk", YESTERDAY, "Direct", 1000.0),
        # R5: next week, created yesterday
        _make_reservation("2026-03-07", "2026-03-08", "Hideaway", "Ogunquit", YESTERDAY, "Airbnb", 200.0),
    ]


@pytest.fixture
def tasks() -> list[dict]:
    return [
        # T1: arrival inspection today
        _make_task(TEST_DATE, "Arrival Inspection - L", "Created", 60, "Ogunquit", "Beach House"),
        # T2: arrival inspection today
        _make_task(TEST_DATE, "Arrival Inspection - M (w/ Inventory)", "Created", 45, "York", "Sea Cottage"),
        # T3: owner stay today — should NOT appear in inspections
        _make_task(TEST_DATE, "Owner Stay Setup", "Created", 30, "York", "Sea Cottage"),
        # T4: overdue cleaning — excluded by department filter (Cleaning dept)
        _make_task(YESTERDAY, "Cleaning", "Overdue", 120, "Kennebunk", "Farm Stay",
                   department="Cleaning"),
        # T5: future inspection
        _make_task("2026-03-05", "Arrival Inspection - E", "Created", 30, "Ogunquit", "Hideaway"),
        # T6: high-priority overdue (Maintenance)
        _make_task(YESTERDAY, "HVAC Repair", "Overdue", 120, "York", "Sea Cottage",
                   department="Maintenance", priority="High"),
        # T7: guest-initiated overdue, stale (last updated 32 days before TEST_DATE)
        _make_task(YESTERDAY, "Guest Request - Extra Towels", "Overdue", 15, "Ogunquit", "Beach House",
                   department="Maintenance", priority="High", requested_by="Guest",
                   last_updated_date="2026-02-01"),
        # T8: future task with assignee (in next-7-day window from TEST_DATE=2026-03-04)
        _make_task("2026-03-06", "Pool Inspection - L", "Created", 45, "York", "Sea Cottage",
                   department="Housekeeping", assignee="Maria Santos"),
    ]


@pytest.fixture
def kpis(reservations: list[dict], tasks: list[dict]) -> dict:
    return compute_kpis(reservations, tasks, TEST_DATE)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_top_level_keys(kpis: dict) -> None:
    assert set(kpis.keys()) == {
        "today", "yesterday_bookings", "revenue",
        "rolling_7_days", "data_quality", "operations_detail", "owner_stays_upcoming",
    }


def test_same_day_turns(kpis: dict) -> None:
    turns = kpis["today"]["same_day_turns"]
    assert len(turns) == 1
    assert turns[0]["listing_name"] == "Sea Cottage"


def test_yesterday_bookings(kpis: dict) -> None:
    yday = kpis["yesterday_bookings"]
    # R1 (500) + R4 (1000) + R5 (200) were all created on YESTERDAY
    assert yday["new_reservation_count"] == 3
    assert yday["new_commission"] == pytest.approx(1700.0)


def test_overdue_tasks(kpis: dict) -> None:
    overdue = kpis["today"]["overdue_tasks"]
    titles = [t["task_title"] for t in overdue]
    # Cleaning tasks are excluded by department filter
    assert "Cleaning" not in titles
    # Maintenance and Inspection tasks are included
    assert "HVAC Repair" in titles
    assert "Guest Request - Extra Towels" in titles


def test_owner_stays_excluded_from_inspections(kpis: dict) -> None:
    today = kpis["today"]
    inspection_titles = [t["task_title"] for t in today["inspections"]]
    owner_stay_titles = [t["task_title"] for t in today["owner_stays"]]

    # T3 must NOT appear in inspections
    assert not any("Owner Stay" in title for title in inspection_titles)
    # T3 must appear in owner_stays
    assert "Owner Stay Setup" in owner_stay_titles


def test_empty_input() -> None:
    result = compute_kpis([], [], TEST_DATE)
    assert set(result.keys()) == {
        "today", "yesterday_bookings", "revenue",
        "rolling_7_days", "data_quality", "operations_detail", "owner_stays_upcoming",
    }
    assert result["today"]["checkins"] == []
    assert result["today"]["same_day_turns"] == []
    assert result["yesterday_bookings"]["new_commission"] == 0.0
    assert result["revenue"]["total_commission"] == 0.0
    assert result["data_quality"]["guesty_available"] is False
    assert result["data_quality"]["breezeway_available"] is False


def test_total_estimated_hours_today(kpis: dict) -> None:
    # T1(60) + T2(45) + T3(30) = 135 min = 2.25 hours
    assert kpis["today"]["total_estimated_hours_today"] == pytest.approx(2.25)


def test_high_priority_overdue(kpis: dict) -> None:
    hp = kpis["today"]["high_priority_overdue"]
    titles = [t["task_title"] for t in hp]
    assert "HVAC Repair" in titles
    assert "Guest Request - Extra Towels" in titles


def test_guest_requests_overdue(kpis: dict) -> None:
    gr = kpis["today"]["guest_requests_overdue"]
    assert len(gr) == 1
    assert gr[0]["task_title"] == "Guest Request - Extra Towels"


def test_operations_detail_keys(kpis: dict) -> None:
    od = kpis["operations_detail"]
    assert set(od.keys()) == {"tasks_by_department_all", "assignee_workload_7_days", "stale_tasks"}


def test_stale_tasks(kpis: dict) -> None:
    stale = kpis["operations_detail"]["stale_tasks"]
    titles = [t["task_title"] for t in stale]
    # T7 last_updated=2026-02-01, cutoff=TEST_DATE-14=2026-02-18 → stale
    assert "Guest Request - Extra Towels" in titles


def test_assignee_workload(kpis: dict) -> None:
    workload = kpis["operations_detail"]["assignee_workload_7_days"]
    # T8 due 2026-03-06, within next 7 days of TEST_DATE=2026-03-04
    assert "Maria Santos" in workload
    assert workload["Maria Santos"] >= 1
