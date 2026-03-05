"""Preview the HTML dashboard using sample data.

Loads guesty_sample.html + breezeway_sample.csv, runs parsers → KPIs →
narrative → dashboard, then writes docs/index.html.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

# Allow running from repo root or scripts/ directory.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.parsers.guesty import parse_guesty_report
from src.parsers.breezeway import parse_breezeway_report
from src.kpi import compute_kpis
from src.narrative import generate_narrative
from src.dashboard import build_dashboard

SAMPLE_DIR = ROOT / "tests" / "sample_data"
GUESTY_HTML = SAMPLE_DIR / "guesty_sample.html"
BREEZEWAY_CSV = SAMPLE_DIR / "breezeway_sample.csv"
OUTPUT_PATH = ROOT / "docs" / "index.html"


def main() -> None:
    report_date = date.today().isoformat()

    # ── Load sample data ────────────────────────────────────────────────────
    if not GUESTY_HTML.exists():
        print(f"ERROR: {GUESTY_HTML} not found. Run scripts/fetch_guesty_sample.py first.")
        sys.exit(1)

    if not BREEZEWAY_CSV.exists():
        print(f"ERROR: {BREEZEWAY_CSV} not found. Run scripts/fetch_breezeway_sample.py first.")
        sys.exit(1)

    print("Loading sample data...")
    guesty_html = GUESTY_HTML.read_text(encoding="utf-8")
    breezeway_csv = BREEZEWAY_CSV.read_text(encoding="utf-8")

    # ── Parse ───────────────────────────────────────────────────────────────
    print("Parsing Guesty report...")
    reservations = parse_guesty_report(guesty_html)
    print(f"  → {len(reservations)} reservations")

    print("Parsing Breezeway report...")
    tasks = parse_breezeway_report(breezeway_csv)
    print(f"  → {len(tasks)} tasks")

    # ── KPIs ────────────────────────────────────────────────────────────────
    print("Computing KPIs...")
    kpis = compute_kpis(reservations, tasks, report_date)
    today = kpis["today"]
    print(f"  → check-ins: {len(today['checkins'])}, "
          f"same-day turns: {len(today['same_day_turns'])}, "
          f"overdue: {len(today['overdue_tasks'])}")

    # ── Narrative ───────────────────────────────────────────────────────────
    print("Generating narrative (may call Anthropic API)...")
    narrative = generate_narrative(kpis, report_date)
    print(f"  → {len(narrative)} characters")

    # ── Dashboard ───────────────────────────────────────────────────────────
    print("Building dashboard HTML...")
    html = build_dashboard(kpis, narrative, report_date)
    print(f"  → {len(html):,} bytes")

    # ── Write ───────────────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"\nDashboard saved to {OUTPUT_PATH} — open in browser")


if __name__ == "__main__":
    main()
