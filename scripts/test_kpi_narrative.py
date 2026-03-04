"""End-to-end smoke test: parse sample data → compute KPIs → generate narrative.

Run from the project root:
    python3 scripts/test_kpi_narrative.py

Requires:
    tests/sample_data/guesty_sample.html  (run: python3 scripts/fetch_guesty_sample.py)
    tests/sample_data/breezeway_sample.csv (run: python3 scripts/fetch_breezeway_sample.py)
    ANTHROPIC_API_KEY in .env or environment
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parsers.guesty import parse_guesty_report
from src.parsers.breezeway import parse_breezeway_report
from src.kpi import compute_kpis
from src.narrative import generate_narrative

GUESTY_SAMPLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "sample_data", "guesty_sample.html",
)
BREEZEWAY_SAMPLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "sample_data", "breezeway_sample.csv",
)


def main() -> None:
    today = date.today().strftime("%Y-%m-%d")
    print(f"Report date: {today}\n")

    # Load and parse Guesty data
    reservations: list[dict] = []
    if os.path.exists(GUESTY_SAMPLE):
        with open(GUESTY_SAMPLE, encoding="utf-8") as f:
            reservations = parse_guesty_report(f.read())
        print(f"Guesty: {len(reservations)} reservations loaded")
    else:
        print("WARNING: guesty_sample.html not found — run fetch_guesty_sample.py")

    # Load and parse Breezeway data
    tasks: list[dict] = []
    if os.path.exists(BREEZEWAY_SAMPLE):
        with open(BREEZEWAY_SAMPLE, encoding="utf-8") as f:
            tasks = parse_breezeway_report(f.read())
        print(f"Breezeway: {len(tasks)} tasks loaded")
    else:
        print("WARNING: breezeway_sample.csv not found — run fetch_breezeway_sample.py")

    print()

    # Compute KPIs
    kpis = compute_kpis(reservations, tasks, today)

    # Print KPI summary (counts, not raw lists)
    today_kpis = kpis["today"]
    yday = kpis["yesterday_bookings"]
    rev = kpis["revenue"]
    dq = kpis["data_quality"]

    print("=" * 55)
    print("KPI SUMMARY")
    print("=" * 55)
    print(f"  Check-ins today:          {len(today_kpis['checkins'])}")
    print(f"  Check-outs today:         {len(today_kpis['checkouts'])}")
    print(f"  Same-day turns:           {len(today_kpis['same_day_turns'])}")
    print(f"  Arrival inspections:      {len(today_kpis['inspections'])}")
    print(f"  Owner stays:              {len(today_kpis['owner_stays'])}")
    print(f"  Overdue tasks:            {len(today_kpis['overdue_tasks'])}")
    print(f"  Est. hours today:         {today_kpis['total_estimated_hours_today']:.1f}h")
    print()
    print(f"  Yesterday's bookings:     {yday['new_reservation_count']} (${yday['new_commission']:,.2f})")
    print(f"  Total commission (all):   ${rev['total_commission']:,.2f}")
    print(f"  MTD commission:           ${rev['mtd_commission']:,.2f}")
    print(f"  Avg per reservation:      ${rev['avg_commission_per_reservation']:,.2f}")
    print()
    print(f"  Guesty data available:    {dq['guesty_available']} ({dq['guesty_reservation_count']} rows)")
    print(f"  Breezeway data available: {dq['breezeway_available']} ({dq['breezeway_task_count']} rows)")
    print("=" * 55)
    print()

    # Generate narrative
    print("Calling Claude API to generate narrative...")
    narrative = generate_narrative(kpis, today)
    print()
    print("=" * 55)
    print("MORNING BRIEFING")
    print("=" * 55)
    print(narrative)


if __name__ == "__main__":
    main()
