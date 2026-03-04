"""Generate a human-readable morning briefing narrative from KPI data via Claude API."""

from __future__ import annotations

import json
import logging
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# User explicitly specified claude-sonnet-4-5
MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = (
    "You are a daily briefing writer for a short-term rental management company "
    "in southern coastal Maine managing 30-50 vacation properties. "
    "Write a concise morning briefing (3-5 paragraphs) highlighting what matters today: "
    "same-day turns that need attention, check-ins/checkouts, yesterday's booking activity, "
    "any overdue tasks or operational issues, and the week ahead. "
    "Be direct, use specific numbers and property names, flag anything unusual or that needs "
    "immediate attention. If any data source is missing, note it. "
    "Tone: professional but warm, like a trusted operations manager giving the morning rundown."
)


def generate_narrative(kpis: dict, report_date: str) -> str:
    """Generate a morning briefing narrative from KPI data using the Claude API.

    Args:
        kpis: KPI dict from compute_kpis().
        report_date: Report date in YYYY-MM-DD format.

    Returns:
        Narrative text string. On API failure, returns a plain-text fallback
        with key numbers extracted from kpis.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; returning fallback narrative")
        return _fallback_narrative(kpis, report_date)

    user_message = (
        f"Report date: {report_date}\n\n"
        f"KPIs:\n{json.dumps(kpis, indent=2, default=str)}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        # Use streaming to avoid HTTP timeouts with large KPI payloads
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            final = stream.get_final_message()

        return final.content[0].text

    except anthropic.AuthenticationError:
        logger.error("Invalid ANTHROPIC_API_KEY — check your .env file")
    except anthropic.RateLimitError:
        logger.error("Anthropic API rate limit reached")
    except anthropic.APIStatusError as e:
        logger.error("Anthropic API error %d: %s", e.status_code, e.message)
    except Exception:
        logger.error("Unexpected error calling Anthropic API", exc_info=True)

    return _fallback_narrative(kpis, report_date)


def _fallback_narrative(kpis: dict, report_date: str) -> str:
    """Return a plain-text summary of key KPI numbers when the API is unavailable.

    Args:
        kpis: KPI dict from compute_kpis().
        report_date: Report date in YYYY-MM-DD format.

    Returns:
        Plain-text briefing string with key counts.
    """
    today = kpis.get("today", {})
    yday = kpis.get("yesterday_bookings", {})
    rev = kpis.get("revenue", {})
    dq = kpis.get("data_quality", {})

    lines = [
        f"=== Daily Briefing — {report_date} (API unavailable) ===",
        "",
        f"Data sources: Guesty {'✓' if dq.get('guesty_available') else '✗'} "
        f"({dq.get('guesty_reservation_count', 0)} reservations)  |  "
        f"Breezeway {'✓' if dq.get('breezeway_available') else '✗'} "
        f"({dq.get('breezeway_task_count', 0)} tasks)",
        "",
        "TODAY",
        f"  Check-ins:       {len(today.get('checkins', []))}",
        f"  Check-outs:      {len(today.get('checkouts', []))}",
        f"  Same-day turns:  {len(today.get('same_day_turns', []))}",
        f"  Inspections:     {len(today.get('inspections', []))}",
        f"  Owner stays:     {len(today.get('owner_stays', []))}",
        f"  Overdue tasks:   {len(today.get('overdue_tasks', []))}",
        f"  Est. hours:      {today.get('total_estimated_hours_today', 0):.1f}h",
        "",
        "YESTERDAY BOOKINGS",
        f"  New reservations: {yday.get('new_reservation_count', 0)}",
        f"  New commission:   ${yday.get('new_commission', 0):,.2f}",
        "",
        "REVENUE (all time)",
        f"  Total commission: ${rev.get('total_commission', 0):,.2f}",
        f"  MTD commission:   ${rev.get('mtd_commission', 0):,.2f}",
        f"  Avg/reservation:  ${rev.get('avg_commission_per_reservation', 0):,.2f}",
    ]
    return "\n".join(lines)
