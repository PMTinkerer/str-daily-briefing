"""Build a compact, inline-styled HTML email summary for the daily briefing."""

from __future__ import annotations

import html
import re
from datetime import datetime


def build_email_html(
    kpis: dict,
    narrative: str,
    report_date: str,
    dashboard_url: str,
) -> str:
    """Build an inline-styled HTML email summary suitable for any email client.

    Args:
        kpis: KPI dict from compute_kpis().
        narrative: Morning briefing text from generate_narrative().
        report_date: Report date in YYYY-MM-DD format.
        dashboard_url: URL to the full dashboard (used for the CTA button).

    Returns:
        Complete HTML string with all styles inline, max-width 600px.
    """
    long_date = datetime.strptime(report_date, "%Y-%m-%d").strftime("%B %-d, %Y")
    today = kpis.get("today", {})

    checkins       = len(today.get("checkins", []))
    checkouts      = len(today.get("checkouts", []))
    turns          = len(today.get("same_day_turns", []))
    overdue        = today.get("overdue_tasks", [])
    hp_overdue     = today.get("high_priority_overdue", [])

    header_html     = _render_header(long_date)
    numbers_html    = _render_key_numbers(checkins, checkouts, turns, len(overdue))
    narrative_html  = _render_narrative(narrative)
    alert_html      = _render_alert(overdue, hp_overdue)
    cta_html        = _render_cta(dashboard_url)
    footer_html     = _render_footer()

    body_content = (
        header_html
        + numbers_html
        + narrative_html
        + alert_html
        + cta_html
        + footer_html
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Briefing — {html.escape(long_date)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation"
       style="background-color:#f1f5f9;">
  <tr>
    <td align="center" style="padding:24px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
             style="max-width:600px;background-color:#ffffff;border-radius:8px;
                    overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.1);">
        {body_content}
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_header(long_date: str) -> str:
    return f"""\
<tr>
  <td style="background-color:#0f172a;padding:28px 32px;">
    <p style="margin:0;color:#94a3b8;font-size:11px;letter-spacing:.1em;
              text-transform:uppercase;">Short-Term Rentals</p>
    <h1 style="margin:6px 0 0;color:#ffffff;font-size:22px;font-weight:700;
               line-height:1.3;">Daily Briefing</h1>
    <p style="margin:4px 0 0;color:#64748b;font-size:14px;">{html.escape(long_date)}</p>
  </td>
</tr>"""


def _render_key_numbers(checkins: int, checkouts: int, turns: int, overdue: int) -> str:
    overdue_color = "#ef4444" if overdue > 0 else "#1e293b"

    def cell(value: int, label: str, color: str = "#1e293b") -> str:
        return f"""\
<td align="center" style="padding:20px 8px;border-right:1px solid #e2e8f0;">
  <p style="margin:0;font-size:28px;font-weight:700;color:{color};">{value}</p>
  <p style="margin:4px 0 0;font-size:11px;color:#64748b;
            text-transform:uppercase;letter-spacing:.05em;">{label}</p>
</td>"""

    return f"""\
<tr>
  <td style="padding:0;">
    <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
      <tr>
        {cell(checkins,  "Check-ins")}
        {cell(checkouts, "Check-outs")}
        {cell(turns,     "Same-day turns")}
        <td align="center" style="padding:20px 8px;">
          <p style="margin:0;font-size:28px;font-weight:700;
                    color:{overdue_color};">{overdue}</p>
          <p style="margin:4px 0 0;font-size:11px;color:#64748b;
                    text-transform:uppercase;letter-spacing:.05em;">Overdue tasks</p>
        </td>
      </tr>
    </table>
  </td>
</tr>
<tr><td style="height:1px;background-color:#e2e8f0;"></td></tr>"""


def _render_narrative(narrative: str) -> str:
    body = _md_to_html(narrative)
    return f"""\
<tr>
  <td style="padding:24px 32px;color:#334155;font-size:15px;line-height:1.7;">
    {body}
  </td>
</tr>"""


def _render_alert(overdue: list, hp_overdue: list) -> str:
    if not overdue and not hp_overdue:
        return ""

    n_overdue = len(overdue)
    n_hp = len(hp_overdue)
    heading = f"&#9888; {n_overdue} overdue task(s)"
    if n_hp:
        heading += f" &mdash; {n_hp} high-priority"

    # Collect unique property names from overdue tasks (max 10)
    props = []
    seen: set[str] = set()
    for t in overdue[:10]:
        name = t.get("property_name", "").strip()
        if name and name not in seen:
            props.append(name)
            seen.add(name)

    items_html = "".join(
        f'<li style="margin:2px 0;">{html.escape(p)}</li>' for p in props
    )
    list_html = f'<ul style="margin:8px 0 0;padding-left:20px;">{items_html}</ul>' if items_html else ""

    return f"""\
<tr>
  <td style="padding:0 32px 16px;">
    <div style="border-left:4px solid #ef4444;background-color:#fef2f2;
                padding:12px 16px;border-radius:4px;">
      <p style="margin:0;font-weight:700;color:#b91c1c;font-size:14px;">{heading}</p>
      {list_html}
    </div>
  </td>
</tr>"""


def _render_cta(dashboard_url: str) -> str:
    safe_url = html.escape(dashboard_url)
    return f"""\
<tr>
  <td align="center" style="padding:24px 32px 32px;">
    <a href="{safe_url}"
       style="display:inline-block;background-color:#0d9488;color:#ffffff;
              font-size:15px;font-weight:700;text-decoration:none;
              padding:14px 32px;border-radius:6px;">
      View Full Dashboard &rarr;
    </a>
  </td>
</tr>"""


def _render_footer() -> str:
    return """\
<tr>
  <td style="background-color:#f8fafc;padding:16px 32px;
             border-top:1px solid #e2e8f0;">
    <p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;">
      Generated by STR Daily Briefing
    </p>
  </td>
</tr>"""


# ---------------------------------------------------------------------------
# Markdown → inline HTML
# ---------------------------------------------------------------------------

def _md_to_html(text: str) -> str:
    """Convert a minimal markdown subset to email-safe inline HTML.

    Handles: ## headings, **bold**, - bullet runs, double-newline paragraphs.
    Applies html.escape() to all user-supplied text before transformation.
    """
    # 1. Escape HTML entities in the raw text first
    escaped = html.escape(text)

    # 2. ## Heading → <h3>
    escaped = re.sub(
        r"(?m)^##\s+(.+)$",
        r'<h3 style="margin:16px 0 4px;font-size:15px;color:#0f172a;">\1</h3>',
        escaped,
    )

    # 3. **bold** → <strong>
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    # 4. Bullet runs (lines starting with "- ") → <ul><li>
    def replace_bullets(m: re.Match) -> str:
        lines = m.group(0).strip().splitlines()
        items = "".join(
            f'<li style="margin:2px 0;">{line.lstrip("- ").strip()}</li>'
            for line in lines
            if line.strip().startswith("- ")
        )
        return f'<ul style="margin:8px 0;padding-left:20px;">{items}</ul>'

    escaped = re.sub(r"(?m)(^- .+\n?)+", replace_bullets, escaped)

    # 5. Double newlines → paragraph breaks
    paragraphs = re.split(r"\n{2,}", escaped.strip())
    result = "".join(
        f'<p style="margin:0 0 12px;">{p.replace(chr(10), " ").strip()}</p>'
        for p in paragraphs
        if p.strip()
    )

    return result
