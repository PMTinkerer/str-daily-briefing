"""Orchestrator: fetch emails → parse → compute → narrate → dashboard → send."""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def run_daily_briefing() -> None:
    """Run the full daily briefing pipeline.

    Fetches Guesty and Breezeway emails, parses them, computes KPIs,
    generates a narrative, builds the dashboard, and sends the email summary.

    Missing data sources are handled gracefully — the pipeline continues
    with whatever data is available and flags gaps in the data quality section.

    Exits with code 1 if Gmail authentication fails or email send fails.
    """
    # Import here to keep startup fast and avoid circular imports
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
    logger.info("Starting daily briefing for %s", report_date)

    # -------------------------------------------------------------------------
    # a. Authenticate — critical failure; nothing else works without this
    # -------------------------------------------------------------------------
    try:
        service = authenticate()
    except Exception:
        logger.critical("Gmail authentication failed — cannot continue", exc_info=True)
        sys.exit(1)

    # -------------------------------------------------------------------------
    # b. Fetch emails (48h window for reliability)
    # -------------------------------------------------------------------------
    guesty_emails = fetch_recent_emails(service, REPORT_SENDER_GUESTY, hours_back=48)
    breezeway_emails = fetch_recent_emails(service, REPORT_SENDER_BREEZEWAY, hours_back=48)

    # -------------------------------------------------------------------------
    # c. Parse — use most-recent email of each type; handle missing gracefully
    # -------------------------------------------------------------------------
    reservations: list[dict] = []
    if guesty_emails:
        body = guesty_emails[0].get("body_html", "")
        if body:
            reservations = parse_guesty_report(body)
            logger.info("Parsed %d Guesty reservation(s)", len(reservations))
        else:
            logger.warning("Guesty email found but body is empty")
    else:
        logger.warning("No Guesty email found in the last 48 hours")

    tasks: list[dict] = []
    if breezeway_emails:
        csv_attachments = [
            a for a in breezeway_emails[0].get("attachments", [])
            if a["filename"].lower().endswith(".csv")
        ]
        if csv_attachments:
            tasks = parse_breezeway_report(csv_attachments[0]["content"])
            logger.info("Parsed %d Breezeway task(s)", len(tasks))
        else:
            logger.warning("Breezeway email found but no CSV attachment present")
    else:
        logger.warning("No Breezeway email found in the last 48 hours")

    # -------------------------------------------------------------------------
    # d. Compute KPIs
    # -------------------------------------------------------------------------
    kpis = compute_kpis(reservations, tasks, report_date)
    dq = kpis.get("data_quality", {})
    logger.info(
        "KPIs computed — Guesty: %s, Breezeway: %s",
        "\u2713" if dq.get("guesty_available") else "\u2717",
        "\u2713" if dq.get("breezeway_available") else "\u2717",
    )

    # -------------------------------------------------------------------------
    # e. Generate narrative
    # -------------------------------------------------------------------------
    narrative = generate_narrative(kpis, report_date)
    logger.info("Narrative generated (%d chars)", len(narrative))

    # -------------------------------------------------------------------------
    # f. Build and save dashboard
    # -------------------------------------------------------------------------
    dashboard_html = build_dashboard(kpis, narrative, report_date)
    dashboard_path = Path("docs/index.html")
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(dashboard_html, encoding="utf-8")
    logger.info("Dashboard saved \u2192 %s (%d bytes)", dashboard_path, len(dashboard_html))

    # -------------------------------------------------------------------------
    # g. Build email summary
    # -------------------------------------------------------------------------
    email_html = build_email_html(kpis, narrative, report_date, DASHBOARD_URL)

    # -------------------------------------------------------------------------
    # h. Send email
    # -------------------------------------------------------------------------
    if not BRIEFING_RECIPIENTS:
        logger.warning("BRIEFING_RECIPIENTS is empty \u2014 skipping email send")
        logger.info("Daily briefing complete (no email sent).")
        return

    subject = (
        "Daily Briefing \u2014 "
        + datetime.strptime(report_date, "%Y-%m-%d").strftime("%B %-d, %Y")
    )
    ok = send_email(service, BRIEFING_RECIPIENTS, subject, email_html)
    if not ok:
        logger.error("Email delivery failed")
        sys.exit(1)

    logger.info("Daily briefing complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    run_daily_briefing()
