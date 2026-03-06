"""Dry-run the full daily briefing pipeline and optionally send the email.

Usage:
    python3 scripts/send_test_email.py

Runs the complete fetch → parse → compute → narrate → dashboard → email
pipeline using real credentials and real data, but pauses before sending.
Prints a summary of the email (recipients, subject, plain-text preview) and
waits for the user to type "send" before delivering.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

# Allow running as a top-level script from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Run dry-run pipeline and prompt before sending."""
    from src.config import (
        BRIEFING_RECIPIENTS,
        DASHBOARD_URL,
        REPORT_SENDER_BREEZEWAY,
        REPORT_SENDER_GUESTY,
    )
    from src.dashboard import build_dashboard
    from src.email_report import build_email_html
    from src.gmail_client import authenticate, fetch_recent_emails, send_email
    from src.kpi import compute_kpis
    from src.narrative import generate_narrative
    from src.parsers.breezeway import parse_breezeway_report
    from src.parsers.guesty import parse_guesty_report

    report_date: str = os.getenv("REPORT_DATE") or date.today().isoformat()

    # ------------------------------------------------------------------
    # Authenticate
    # ------------------------------------------------------------------
    print("\nAuthenticating with Gmail...")
    try:
        service = authenticate()
    except Exception as exc:
        print(f"ERROR: Gmail authentication failed — {exc}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------
    print("Fetching emails (last 48 hours)...")
    guesty_emails = fetch_recent_emails(service, REPORT_SENDER_GUESTY, hours_back=48)
    breezeway_emails = fetch_recent_emails(service, REPORT_SENDER_BREEZEWAY, hours_back=48)

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------
    reservations: list[dict] = []
    if guesty_emails:
        body = guesty_emails[0].get("body_html", "")
        if body:
            reservations = parse_guesty_report(body)
    else:
        print("  WARNING: No Guesty email found")

    tasks: list[dict] = []
    if breezeway_emails:
        csv_atts = [
            a for a in breezeway_emails[0].get("attachments", [])
            if a["filename"].lower().endswith(".csv")
        ]
        if csv_atts:
            tasks = parse_breezeway_report(csv_atts[0]["content"])
    else:
        print("  WARNING: No Breezeway email found")

    print(f"  Reservations: {len(reservations)}  |  Tasks: {len(tasks)}")

    # ------------------------------------------------------------------
    # KPIs → narrative → dashboard
    # ------------------------------------------------------------------
    print("Computing KPIs and generating narrative...")
    kpis = compute_kpis(reservations, tasks, report_date)
    narrative = generate_narrative(kpis, report_date)

    print("Building dashboard...")
    dashboard_html = build_dashboard(kpis, narrative, report_date)
    dashboard_path = Path("docs/index.html")
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(dashboard_html, encoding="utf-8")
    print(f"  Dashboard saved → {dashboard_path} ({len(dashboard_html):,} bytes)")

    # ------------------------------------------------------------------
    # Build email
    # ------------------------------------------------------------------
    email_html = build_email_html(kpis, narrative, report_date, DASHBOARD_URL)
    subject = (
        "Daily Briefing \u2014 "
        + datetime.strptime(report_date, "%Y-%m-%d").strftime("%B %-d, %Y")
    )

    # Plain-text preview (strip HTML tags)
    preview = re.sub(r"<[^>]+>", " ", email_html)
    preview = re.sub(r"\s+", " ", preview).strip()[:500]

    # ------------------------------------------------------------------
    # Dry-run summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("DRY RUN \u2014 Daily Briefing")
    print("=" * 60)
    if BRIEFING_RECIPIENTS:
        print(f"Recipients : {', '.join(BRIEFING_RECIPIENTS)}")
    else:
        print("Recipients : (none — BRIEFING_RECIPIENTS is empty)")
    print(f"Subject    : {subject}")
    print(f"Email size : {len(email_html):,} bytes")
    print("\nPreview (first 500 chars, tags stripped):")
    print("-" * 60)
    print(preview)
    print("-" * 60)

    if not BRIEFING_RECIPIENTS:
        print("\nNo recipients configured. Set BRIEFING_RECIPIENTS in .env to enable sending.")
        return

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------
    try:
        answer = input('\nType "send" to deliver, anything else to cancel: ').strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return

    if answer != "send":
        print("Cancelled.")
        return

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------
    ok = send_email(service, BRIEFING_RECIPIENTS, subject, email_html)
    if ok:
        print(f"Email sent successfully to {len(BRIEFING_RECIPIENTS)} recipient(s).")
    else:
        print("ERROR: Email send failed. Check logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
