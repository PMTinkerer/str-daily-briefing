"""Compute KPI snapshot from parsed Guesty reservation and Breezeway task data."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, timedelta

logger = logging.getLogger(__name__)

_OVERDUE_DEPARTMENTS = {"Maintenance", "Inspection"}


def compute_kpis(
    guesty_reservations: list[dict],
    breezeway_tasks: list[dict],
    report_date: str,
) -> dict:
    """Aggregate parsed data into a structured KPI snapshot.

    Args:
        guesty_reservations: List of reservation dicts from parse_guesty_report().
        breezeway_tasks: List of task dicts from parse_breezeway_report().
        report_date: Date for "today" in YYYY-MM-DD format.

    Returns:
        Dict with sections: today, yesterday_bookings, revenue,
        rolling_7_days, data_quality.
    """
    today = report_date
    yesterday = (date.fromisoformat(report_date) - timedelta(days=1)).strftime("%Y-%m-%d")
    report_month = report_date[:7]  # "YYYY-MM"
    next_7 = [
        (date.fromisoformat(report_date) + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(7)
    ]

    return {
        "today": _compute_today(guesty_reservations, breezeway_tasks, today),
        "yesterday_bookings": _compute_yesterday_bookings(guesty_reservations, yesterday),
        "revenue": _compute_revenue(guesty_reservations, report_month),
        "rolling_7_days": _compute_rolling_7_days(guesty_reservations, breezeway_tasks, next_7),
        "operations_detail": _compute_operations_detail(breezeway_tasks, next_7, today),
        "data_quality": {
            "guesty_available": bool(guesty_reservations),
            "breezeway_available": bool(breezeway_tasks),
            "guesty_reservation_count": len(guesty_reservations),
            "breezeway_task_count": len(breezeway_tasks),
        },
    }


def _compute_today(
    reservations: list[dict],
    tasks: list[dict],
    today: str,
) -> dict:
    """Build the 'today' KPI section."""
    checkins = [r for r in reservations if r["check_in"] == today]
    checkouts = [r for r in reservations if r["check_out"] == today]

    # Same-day turns: listing_name appears in both checkouts AND checkins today
    checkout_names = {r["listing_name"] for r in checkouts}
    checkin_names = {r["listing_name"] for r in checkins}
    turn_names = checkout_names & checkin_names
    same_day_turns = [
        {"listing_name": r["listing_name"], "city": r["city"]}
        for r in checkins
        if r["listing_name"] in turn_names
    ]

    tasks_due_today = [t for t in tasks if t["due_date"] == today]
    inspections = [
        t for t in tasks_due_today
        if "Arrival Inspection" in t["task_title"]
        and "Owner Stay" not in t["task_title"]
    ]
    owner_stays = [t for t in tasks_due_today if "Owner Stay" in t["task_title"]]
    overdue_tasks = [
        t for t in tasks
        if (t["status"] == "Overdue"
            or (t["due_date"] and t["due_date"] < today))
        and t.get("department", "") in _OVERDUE_DEPARTMENTS
    ]
    high_priority_overdue = [
        t for t in overdue_tasks
        if t.get("priority", "").lower() == "high"
    ]
    guest_requests_overdue = [
        t for t in overdue_tasks
        if t.get("requested_by", "").strip().lower() == "guest"
    ]
    tasks_by_department = dict(Counter(
        t.get("department", "") or "Unknown"
        for t in tasks_due_today
    ))
    total_estimated_hours_today = sum(
        t["estimated_time_minutes"] for t in tasks_due_today
    ) / 60

    return {
        "checkins": checkins,
        "checkouts": checkouts,
        "same_day_turns": same_day_turns,
        "inspections": inspections,
        "owner_stays": owner_stays,
        "overdue_tasks": overdue_tasks,
        "high_priority_overdue": high_priority_overdue,
        "guest_requests_overdue": guest_requests_overdue,
        "tasks_by_department": tasks_by_department,
        "total_estimated_hours_today": round(total_estimated_hours_today, 2),
    }


def _compute_yesterday_bookings(reservations: list[dict], yesterday: str) -> dict:
    """Build the 'yesterday_bookings' KPI section."""
    created_yesterday = [r for r in reservations if r["creation_date"] == yesterday]
    new_commission = sum(r["commission"] for r in created_yesterday)
    by_platform = dict(Counter(r["platform"] for r in created_yesterday))

    return {
        "new_commission": round(new_commission, 2),
        "new_reservation_count": len(created_yesterday),
        "by_platform": by_platform,
    }


def _compute_revenue(reservations: list[dict], report_month: str) -> dict:
    """Build the 'revenue' KPI section."""
    total_commission = sum(r["commission"] for r in reservations)
    mtd_commission = sum(
        r["commission"] for r in reservations
        if r["check_in"].startswith(report_month)
    )
    count = len(reservations)
    avg = total_commission / count if count else 0.0

    # commission_by_property: accumulate then take top 10
    prop_totals: dict[str, float] = {}
    for r in reservations:
        prop_totals[r["listing_name"]] = prop_totals.get(r["listing_name"], 0.0) + r["commission"]
    top_10 = dict(
        sorted(prop_totals.items(), key=lambda kv: kv[1], reverse=True)[:10]
    )

    platform_totals: dict[str, float] = {}
    for r in reservations:
        platform_totals[r["platform"]] = platform_totals.get(r["platform"], 0.0) + r["commission"]

    return {
        "total_commission": round(total_commission, 2),
        "mtd_commission": round(mtd_commission, 2),
        "avg_commission_per_reservation": round(avg, 2),
        "commission_by_property": {k: round(v, 2) for k, v in top_10.items()},
        "commission_by_platform": {k: round(v, 2) for k, v in platform_totals.items()},
    }


def _compute_rolling_7_days(
    reservations: list[dict],
    tasks: list[dict],
    next_7: list[str],
) -> dict:
    """Build the 'rolling_7_days' KPI section."""
    checkins_by_city: dict[str, dict[str, int]] = {}
    same_day_turns_by_city: dict[str, dict[str, int]] = {}
    inspections_by_city: dict[str, dict[str, int]] = {}
    owner_stays_by_day: dict[str, list[str]] = {}

    for day in next_7:
        # Checkins by city (with property names for expandable table)
        day_checkins = [r for r in reservations if r["check_in"] == day]
        city_groups: dict[str, list[str]] = {}
        for r in day_checkins:
            city_groups.setdefault(r["city"], []).append(r["listing_name"])
        checkins_by_city[day] = {
            city: {"count": len(props), "properties": sorted(props)}
            for city, props in city_groups.items()
        }

        # Same-day turns by city
        day_checkouts = [r for r in reservations if r["check_out"] == day]
        checkout_names = {r["listing_name"] for r in day_checkouts}
        checkin_names = {r["listing_name"] for r in day_checkins}
        turn_names = checkout_names & checkin_names
        turn_cities = [
            r["city"] for r in day_checkins if r["listing_name"] in turn_names
        ]
        same_day_turns_by_city[day] = dict(Counter(turn_cities))

        # Arrival inspections by city (exclude escalations)
        day_inspections = [
            t for t in tasks
            if t["due_date"] == day
            and "Arrival Inspection" in t["task_title"]
            and "Escalation" not in t["task_title"]
        ]
        inspections_by_city[day] = dict(Counter(t["city"] for t in day_inspections))

        # Owner stays (only include dates with at least one)
        day_owner_stays = [
            t["property_name"] for t in tasks
            if t["due_date"] == day and "Owner Stay" in t["task_title"]
        ]
        if day_owner_stays:
            owner_stays_by_day[day] = day_owner_stays

    return {
        "checkins_by_city": checkins_by_city,
        "same_day_turns_by_city": same_day_turns_by_city,
        "inspections_by_city": inspections_by_city,
        "owner_stays_by_day": owner_stays_by_day,
    }


def _compute_operations_detail(tasks: list[dict], next_7: list[str], today: str) -> dict:
    """Build the 'operations_detail' KPI section.

    Args:
        tasks: All Breezeway tasks from parse_breezeway_report().
        next_7: List of 7 YYYY-MM-DD date strings starting from today.
        today: Report date in YYYY-MM-DD format.

    Returns:
        Dict with keys: tasks_by_department_all, assignee_workload_7_days, stale_tasks.
    """
    stale_cutoff = (date.fromisoformat(today) - timedelta(days=14)).strftime("%Y-%m-%d")

    dept_all: dict[str, int] = {}
    for t in tasks:
        dept = t.get("department", "") or "Unknown"
        dept_all[dept] = dept_all.get(dept, 0) + 1

    assignee_workload: dict[str, int] = {}
    for t in tasks:
        if t["due_date"] in next_7 and t.get("assignee", "").strip():
            name = t["assignee"].strip()
            assignee_workload[name] = assignee_workload.get(name, 0) + 1

    stale = [
        t for t in tasks
        if t.get("last_updated_date") and t["last_updated_date"] < stale_cutoff
        and t.get("department", "") in _OVERDUE_DEPARTMENTS
    ]

    return {
        "tasks_by_department_all": dept_all,
        "assignee_workload_7_days": assignee_workload,
        "stale_tasks": stale,
    }
