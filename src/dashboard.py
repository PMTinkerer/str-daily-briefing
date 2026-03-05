"""Build a single-file HTML dashboard from KPI data."""

from __future__ import annotations

# ┌─────────────────────────────────────────────────────────────────┐
# │  LAYOUT MAP — build_dashboard() renders sections in this order: │
# │                                                                 │
# │   1. HEAD           — <head> tag, CSS, CDN links                │
# │   2. HEADER         — Title bar + date                          │
# │   3. QUALITY BANNER — Warning strip if data sources missing     │
# │   4. NARRATIVE      — Claude-generated morning briefing text    │
# │   5. TODAY CARDS    — 6 stat cards (check-ins, turns, etc.)    │
# │   6. OWNER STAYS    — Next-7-day owner stays table              │
# │   7. CHARTS         — 4 Chart.js charts (2×2 grid)             │
# │   8. ROLLING TABLES — 7-day check-ins/turns/inspections tables │
# │   9. OVERDUE TASKS  — Red-accented overdue task table           │
# │  10. FOOTER         — Generation timestamp                      │
# │  11. SCRIPTS        — Chart.js init + IntersectionObserver     │
# └─────────────────────────────────────────────────────────────────┘

import html
import json
import logging
import re
from datetime import date, datetime

logger = logging.getLogger(__name__)

# City color palette for charts (cycles if more cities than colors)
_CITY_COLORS = [
    "#2ba5b5", "#e67e22", "#9b59b6", "#27ae60", "#e74c3c",
    "#3498db", "#f1c40f", "#1abc9c", "#e91e63", "#607d8b",
]


def build_dashboard(kpis: dict, narrative: str, report_date: str) -> str:
    """Build a single-file HTML dashboard from KPI data.

    Args:
        kpis: KPI dict from compute_kpis().
        narrative: Morning briefing text from generate_narrative().
        report_date: Report date in YYYY-MM-DD format.

    Returns:
        Complete HTML string (self-contained, CDN links only for Chart.js
        and Google Fonts).
    """
    today_kpis = kpis.get("today", {})
    yday = kpis.get("yesterday_bookings", {})
    rev = kpis.get("revenue", {})
    r7 = kpis.get("rolling_7_days", {})
    dq = kpis.get("data_quality", {})

    report_date_obj = date.fromisoformat(report_date)
    formatted_date = f"{report_date_obj.strftime('%A, %B')} {report_date_obj.day}, {report_date_obj.year}"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    checkins = today_kpis.get("checkins", [])
    checkouts = today_kpis.get("checkouts", [])
    turns = today_kpis.get("same_day_turns", [])
    inspections = today_kpis.get("inspections", [])
    owner_stays_today = today_kpis.get("owner_stays", [])
    overdue = today_kpis.get("overdue_tasks", [])
    est_hours = today_kpis.get("total_estimated_hours_today", 0.0)

    # Sort overdue tasks most-overdue first
    def _days_overdue(task: dict) -> int:
        try:
            return (report_date_obj - date.fromisoformat(task["due_date"])).days
        except (ValueError, KeyError):
            return 0

    overdue_sorted = sorted(overdue, key=_days_overdue, reverse=True)

    html_parts = [
        _render_head(formatted_date),
        _render_header(formatted_date),
        _render_quality_banner(dq),
        _render_narrative(narrative),
        _render_today_cards(
            checkins, checkouts, turns, yday, overdue, est_hours,
            inspections, owner_stays_today,
        ),
        _render_owner_stays(r7),
        _render_charts_section(rev, yday, today_kpis, dq, r7, report_date),
        _render_rolling_tables(r7, report_date),
        _render_overdue_table(overdue_sorted, report_date_obj),
        _render_footer(generated_at),
        _render_scripts(rev, yday, today_kpis, dq, r7, report_date),
        "</body></html>",
    ]

    return "\n".join(html_parts)


# ══════════════════════════════════════════════
# SECTION: Head
# ══════════════════════════════════════════════

def _render_head(formatted_date: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>STR Daily Briefing — {html.escape(formatted_date)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{_css()}
</style>
</head>
<body>"""


# ══════════════════════════════════════════════
# SECTION: Header
# ══════════════════════════════════════════════

def _render_header(formatted_date: str) -> str:
    return f"""<header class="site-header">
  <div class="header-inner">
    <div class="header-logo">🏖</div>
    <h1>Grand Welcome STR<br><span class="header-sub">Daily Briefing</span></h1>
    <p class="header-date">{html.escape(formatted_date)}</p>
  </div>
</header>"""


# ══════════════════════════════════════════════
# SECTION: Data Quality Banner
# ══════════════════════════════════════════════

def _render_quality_banner(dq: dict) -> str:
    missing = []
    if not dq.get("guesty_available"):
        missing.append("Guesty (reservation data)")
    if not dq.get("breezeway_available"):
        missing.append("Breezeway (task data)")
    if not missing:
        return ""
    sources = " and ".join(html.escape(s) for s in missing)
    return f"""<div class="quality-banner">
  ⚠️ <strong>Data Warning:</strong> {sources} {'is' if len(missing) == 1 else 'are'} unavailable.
  Numbers below may be incomplete.
</div>"""


# ══════════════════════════════════════════════
# SECTION: Narrative
# ══════════════════════════════════════════════

def _markdown_to_html(text: str) -> str:
    """Convert a Markdown subset to HTML for the narrative section.

    Handles: ## / ### headers, **bold**, - bullet lists, blank-line paragraphs.
    All text content is HTML-escaped before conversion so user data is safe.
    """
    def _inline(raw: str) -> str:
        """Escape content then apply inline bold conversion."""
        escaped = html.escape(raw)
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)

    lines = text.split("\n")
    parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Empty line → close open list, emit paragraph break
        if not stripped:
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append("")
            continue

        # ## or ### header
        m = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m:
            if in_list:
                parts.append("</ul>")
                in_list = False
            tag = "h3" if len(m.group(1)) <= 2 else "h4"
            parts.append(f"<{tag}>{_inline(m.group(2))}</{tag}>")
            continue

        # - or * bullet
        m = re.match(r"^[-*]\s+(.+)$", stripped)
        if m:
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{_inline(m.group(1))}</li>")
            continue

        # Regular paragraph
        if in_list:
            parts.append("</ul>")
            in_list = False
        parts.append(f"<p>{_inline(stripped)}</p>")

    if in_list:
        parts.append("</ul>")

    return "\n".join(p for p in parts if p != "")


def _render_narrative(narrative: str) -> str:
    body = _markdown_to_html(narrative)
    return f"""<section class="section fade-in">
  <h2 class="section-title">Morning Briefing</h2>
  <div class="narrative-card">
    <div class="narrative-accent"></div>
    <div class="narrative-body">{body}</div>
  </div>
</section>"""


# ══════════════════════════════════════════════
# SECTION: Today at a Glance
# ══════════════════════════════════════════════

def _render_today_cards(
    checkins: list,
    checkouts: list,
    turns: list,
    yday: dict,
    overdue: list,
    est_hours: float,
    inspections: list,
    owner_stays_today: list,
) -> str:
    def _names(items: list, key: str = "listing_name") -> str:
        if not items:
            return '<span class="empty">None today</span>'
        return "<ul class='prop-list'>" + "".join(
            f"<li>{html.escape(str(r.get(key, '')))}</li>" for r in items
        ) + "</ul>"

    turn_modifier = " card--warn" if turns else ""
    overdue_modifier = " card--alert" if overdue else ""

    new_commission = yday.get("new_commission", 0.0)
    new_count = yday.get("new_reservation_count", 0)

    return f"""<section class="section fade-in">
  <h2 class="section-title">Today at a Glance</h2>
  <div class="card-grid">

    <div class="card">
      <div class="card-label">Check-ins</div>
      <div class="card-value">{len(checkins)}</div>
      {_names(checkins)}
    </div>

    <div class="card">
      <div class="card-label">Check-outs</div>
      <div class="card-value">{len(checkouts)}</div>
      {_names(checkouts)}
    </div>

    <div class="card{turn_modifier}">
      <div class="card-label">Same-Day Turns</div>
      <div class="card-value">{len(turns)}</div>
      {_names(turns)}
    </div>

    <div class="card">
      <div class="card-label">Yesterday's Bookings</div>
      <div class="card-value">{new_count}</div>
      <div class="card-detail">${new_commission:,.2f} commission</div>
    </div>

    <div class="card{overdue_modifier}">
      <div class="card-label">Overdue Tasks</div>
      <div class="card-value">{len(overdue)}</div>
      <div class="card-detail">{'Requires attention' if overdue else 'All clear'}</div>
    </div>

    <div class="card">
      <div class="card-label">Est. Hours Today</div>
      <div class="card-value">{est_hours:.1f}h</div>
      <div class="card-detail">{len(inspections)} inspections · {len(owner_stays_today)} owner stays</div>
    </div>

  </div>
</section>"""


# ══════════════════════════════════════════════
# SECTION: Charts
# ══════════════════════════════════════════════

def _render_charts_section(
    rev: dict,
    yday: dict,
    today_kpis: dict,
    dq: dict,
    r7: dict,
    report_date: str,
) -> str:
    return """<section class="section fade-in">
  <h2 class="section-title">Charts</h2>
  <div class="charts-grid">
    <div class="chart-card">
      <h3 class="chart-title">Commission by Platform</h3>
      <canvas id="chartPlatform"></canvas>
    </div>
    <div class="chart-card">
      <h3 class="chart-title">7-Day Check-ins by City</h3>
      <canvas id="chartCheckins"></canvas>
    </div>
    <div class="chart-card">
      <h3 class="chart-title">Tasks Overview</h3>
      <canvas id="chartTasks"></canvas>
    </div>
    <div class="chart-card">
      <h3 class="chart-title">Yesterday's Bookings by Platform</h3>
      <canvas id="chartYesterday"></canvas>
    </div>
  </div>
</section>"""


# ══════════════════════════════════════════════
# SECTION: Rolling 7-Day Tables
# ══════════════════════════════════════════════

def _render_rolling_tables(r7: dict, report_date: str) -> str:
    checkins_by_city = r7.get("checkins_by_city", {})
    turns_by_city = r7.get("same_day_turns_by_city", {})
    inspections_by_city = r7.get("inspections_by_city", {})
    dates = sorted(checkins_by_city.keys())

    if not dates:
        return ""

    def _table(by_city: dict, title: str) -> str:
        all_cities = sorted({
            city
            for day_data in by_city.values()
            for city in day_data
        })
        if not all_cities:
            return f"<h3 class='table-subtitle'>{html.escape(title)}</h3><p class='empty'>No data</p>"

        header_cells = "".join(
            f'<th class="{"today-col" if d == report_date else ""}">'
            f'{_fmt_short_date(d)}</th>'
            for d in dates
        )
        total_row = "".join(
            f'<td class="{"today-col" if d == report_date else ""}">'
            f'{sum(by_city.get(d, {}).values())}</td>'
            for d in dates
        )
        city_rows = ""
        for city in all_cities:
            cells = "".join(
                f'<td class="{"today-col" if d == report_date else ""}">'
                f'{by_city.get(d, {}).get(city, 0)}</td>'
                for d in dates
            )
            city_rows += f"<tr><td class='city-cell'>{html.escape(city)}</td>{cells}</tr>"

        return f"""<h3 class="table-subtitle">{html.escape(title)}</h3>
<div class="table-wrap">
<table class="data-table">
  <thead><tr><th>City</th>{header_cells}</tr></thead>
  <tbody>
    {city_rows}
    <tr class="total-row"><td>Total</td>{total_row}</tr>
  </tbody>
</table>
</div>"""

    return f"""<section class="section fade-in">
  <h2 class="section-title">Rolling 7-Day Outlook</h2>
  {_table(checkins_by_city, "Check-ins by City")}
  <div class="table-spacer"></div>
  {_table(turns_by_city, "Same-Day Turns by City")}
  <div class="table-spacer"></div>
  {_table(inspections_by_city, "Arrival Inspections by City")}
</section>"""


# ══════════════════════════════════════════════
# SECTION: Owner Stays — Next 7 Days
# ══════════════════════════════════════════════

def _render_owner_stays(r7: dict) -> str:
    owner_stays_by_day = r7.get("owner_stays_by_day", {})

    # Flatten dict[date, list[property]] → sorted list of (date, property) tuples
    rows_data: list[tuple[str, str]] = [
        (day, prop)
        for day in sorted(owner_stays_by_day.keys())
        for prop in owner_stays_by_day[day]
    ]

    if rows_data:
        rows_html = "".join(
            f'<tr><td class="os-date">{_fmt_short_date(day)}</td>'
            f'<td class="os-prop">{html.escape(prop)}</td></tr>'
            for day, prop in rows_data
        )
    else:
        rows_html = '<tr><td colspan="2" class="os-empty">No owner stays scheduled</td></tr>'

    return f"""<section class="section fade-in">
  <h2 class="section-title section-title--owner">Owner Stays — Next 7 Days</h2>
  <div class="owner-table-wrap">
    <table class="owner-table">
      <thead><tr><th>Date</th><th>Property</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</section>"""


# ══════════════════════════════════════════════
# SECTION: Overdue Tasks
# ══════════════════════════════════════════════

def _render_overdue_table(overdue_sorted: list, report_date_obj: date) -> str:
    if not overdue_sorted:
        return ""

    rows = ""
    for task in overdue_sorted:
        days = max(0, (report_date_obj - date.fromisoformat(task["due_date"])).days) if task.get("due_date") else 0
        link_html = (
            f'<a href="{html.escape(task["task_report_link"])}" '
            f'target="_blank" class="task-link">View ↗</a>'
            if task.get("task_report_link")
            else "—"
        )
        rows += f"""<tr>
  <td>{html.escape(task.get('property_name', ''))}</td>
  <td>{html.escape(task.get('task_title', ''))}</td>
  <td>{html.escape(task.get('due_date', ''))}</td>
  <td class="days-overdue">{days}d</td>
  <td>{link_html}</td>
</tr>"""

    return f"""<section class="section fade-in">
  <h2 class="section-title section-title--alert">⚠ Overdue Tasks</h2>
  <div class="table-wrap">
  <table class="data-table overdue-table">
    <thead>
      <tr>
        <th>Property</th>
        <th>Task</th>
        <th>Due Date</th>
        <th>Days Overdue</th>
        <th>Link</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</section>"""


# ══════════════════════════════════════════════
# SECTION: Footer
# ══════════════════════════════════════════════

def _render_footer(generated_at: str) -> str:
    return f"""<footer class="site-footer">
  <p>Generated by <strong>STR Daily Briefing</strong> · {html.escape(generated_at)} · Powered by Claude AI</p>
</footer>"""


# ══════════════════════════════════════════════
# SECTION: Scripts (Chart.js + Animations)
# ══════════════════════════════════════════════

def _render_scripts(
    rev: dict,
    yday: dict,
    today_kpis: dict,
    dq: dict,
    r7: dict,
    report_date: str,
) -> str:
    # Build chart data in Python, inject as JSON
    platform_data = _build_platform_chart_data(rev)
    checkins_data = _build_checkins_chart_data(r7, report_date)
    tasks_data = _build_tasks_chart_data(today_kpis, dq)
    yesterday_data = _build_yesterday_chart_data(yday)

    return f"""<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
// ── Injected data ───────────────────────────────────────────────
const PLATFORM_DATA = {json.dumps(platform_data)};
const CHECKINS_DATA = {json.dumps(checkins_data)};
const TASKS_DATA    = {json.dumps(tasks_data)};
const YESTERDAY_DATA = {json.dumps(yesterday_data)};

// ── Chart defaults ──────────────────────────────────────────────
Chart.defaults.color = '#8892a4';
Chart.defaults.borderColor = '#2d3550';
Chart.defaults.font.family = "'Inter', sans-serif";

const TEAL = '#2ba5b5';
const ALERT = '#e74c3c';
const WARN = '#f39c12';

// Commission by Platform (horizontal bar)
new Chart(document.getElementById('chartPlatform'), {{
  type: 'bar',
  data: {{
    labels: PLATFORM_DATA.labels,
    datasets: [{{
      label: 'Commission ($)',
      data: PLATFORM_DATA.data,
      backgroundColor: TEAL,
      borderRadius: 4,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ callback: v => '$' + v.toLocaleString() }} }},
      y: {{ grid: {{ display: false }} }},
    }}
  }}
}});

// 7-day check-ins by city (stacked bar)
new Chart(document.getElementById('chartCheckins'), {{
  type: 'bar',
  data: CHECKINS_DATA,
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    scales: {{
      x: {{ stacked: true, grid: {{ display: false }} }},
      y: {{ stacked: true, ticks: {{ stepSize: 1 }} }},
    }}
  }}
}});

// Tasks overview (doughnut)
new Chart(document.getElementById('chartTasks'), {{
  type: 'doughnut',
  data: {{
    labels: TASKS_DATA.labels,
    datasets: [{{
      data: TASKS_DATA.data,
      backgroundColor: TASKS_DATA.colors,
      borderWidth: 2,
      borderColor: '#232a3b',
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom' }} }},
    cutout: '60%',
  }}
}});

// Yesterday's bookings by platform (bar)
new Chart(document.getElementById('chartYesterday'), {{
  type: 'bar',
  data: {{
    labels: YESTERDAY_DATA.labels,
    datasets: [{{
      label: 'Reservations',
      data: YESTERDAY_DATA.data,
      backgroundColor: TEAL,
      borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ display: false }} }},
      y: {{ ticks: {{ stepSize: 1 }} }},
    }}
  }}
}});

// ── Scroll fade-in ──────────────────────────────────────────────
const observer = new IntersectionObserver(
  entries => entries.forEach(e => {{ if (e.isIntersecting) e.target.classList.add('visible'); }}),
  {{ threshold: 0.08 }}
);
document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));
</script>"""


# ══════════════════════════════════════════════
# SECTION: Chart Data Builders
# ══════════════════════════════════════════════

def _build_platform_chart_data(rev: dict) -> dict:
    by_platform = rev.get("commission_by_platform", {})
    sorted_items = sorted(by_platform.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "labels": [k for k, _ in sorted_items],
        "data": [v for _, v in sorted_items],
    }


def _build_checkins_chart_data(r7: dict, report_date: str) -> dict:
    checkins_by_city = r7.get("checkins_by_city", {})
    dates = sorted(checkins_by_city.keys())
    all_cities = sorted({
        city for day_data in checkins_by_city.values() for city in day_data
    })
    labels = [_fmt_short_date(d) for d in dates]
    datasets = []
    for i, city in enumerate(all_cities):
        color = _CITY_COLORS[i % len(_CITY_COLORS)]
        datasets.append({
            "label": city,
            "data": [checkins_by_city.get(d, {}).get(city, 0) for d in dates],
            "backgroundColor": color,
            "borderRadius": 2,
        })
    return {"labels": labels, "datasets": datasets}


def _build_tasks_chart_data(today_kpis: dict, dq: dict) -> dict:
    overdue_count = len(today_kpis.get("overdue_tasks", []))
    active_count = len(today_kpis.get("inspections", [])) + len(today_kpis.get("owner_stays", []))
    total = dq.get("breezeway_task_count", 0)
    other = max(0, total - overdue_count - active_count)

    labels, data, colors = [], [], []
    if overdue_count:
        labels.append("Overdue")
        data.append(overdue_count)
        colors.append("#e74c3c")
    if active_count:
        labels.append("Active Today")
        data.append(active_count)
        colors.append("#2ba5b5")
    if other:
        labels.append("Other")
        data.append(other)
        colors.append("#4a5568")
    if not data:
        labels, data, colors = ["No Data"], [1], ["#4a5568"]

    return {"labels": labels, "data": data, "colors": colors}


def _build_yesterday_chart_data(yday: dict) -> dict:
    by_platform = yday.get("by_platform", {})
    sorted_items = sorted(by_platform.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "labels": [k for k, _ in sorted_items] or ["None"],
        "data": [v for _, v in sorted_items] or [0],
    }


# ══════════════════════════════════════════════
# SECTION: Date Helpers
# ══════════════════════════════════════════════

def _fmt_short_date(date_str: str) -> str:
    """Format 'YYYY-MM-DD' as 'Mon 3/4'."""
    try:
        d = date.fromisoformat(date_str)
        return f"{d.strftime('%a')} {d.month}/{d.day}"
    except ValueError:
        return date_str


def _fmt_long_date(date_str: str) -> str:
    """Format 'YYYY-MM-DD' as 'Wednesday, March 4'."""
    try:
        d = date.fromisoformat(date_str)
        return f"{d.strftime('%A, %B')} {d.day}"
    except ValueError:
        return date_str


# ══════════════════════════════════════════════
# SECTION: CSS Styles
# ══════════════════════════════════════════════

def _css() -> str:
    return """
:root {
  --bg: #1a1f2e;
  --surface: #232a3b;
  --surface2: #2d3550;
  --teal: #2ba5b5;
  --teal-dim: rgba(43,165,181,0.15);
  --alert: #e74c3c;
  --alert-dim: rgba(231,76,60,0.15);
  --warn: #f39c12;
  --warn-dim: rgba(243,156,18,0.15);
  --text: #e8eaf0;
  --muted: #8892a4;
  --border: #2d3550;
  --radius: 10px;
  --owner: #9b59b6;
  --owner-dim: rgba(155,89,182,0.15);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', sans-serif;
  font-size: 15px;
  line-height: 1.6;
  min-height: 100vh;
}

/* ── Header ── */
.site-header {
  background: linear-gradient(135deg, #0f1320 0%, #1a2540 50%, #1a1f2e 100%);
  border-bottom: 1px solid var(--border);
  padding: 2rem 1.5rem 1.5rem;
  text-align: center;
}
.header-inner { max-width: 900px; margin: 0 auto; }
.header-logo { font-size: 2.5rem; margin-bottom: 0.5rem; }
.site-header h1 {
  font-size: clamp(1.6rem, 4vw, 2.4rem);
  font-weight: 700;
  color: var(--text);
  line-height: 1.2;
  letter-spacing: -0.5px;
}
.header-sub { color: var(--teal); }
.header-date {
  margin-top: 0.5rem;
  color: var(--muted);
  font-size: 1rem;
  font-weight: 500;
}

/* ── Quality banner ── */
.quality-banner {
  background: var(--warn-dim);
  border: 1px solid var(--warn);
  color: var(--warn);
  padding: 0.75rem 1.5rem;
  text-align: center;
  font-size: 0.9rem;
}

/* ── Layout ── */
.section {
  max-width: 1100px;
  margin: 2rem auto;
  padding: 0 1.25rem;
}
.section-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--teal);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}
.section-title--alert { color: var(--alert); }
.section-title--owner { color: var(--owner); }

/* ── Fade-in animation ── */
.fade-in { opacity: 0; transform: translateY(16px); transition: opacity 0.5s ease, transform 0.5s ease; }
.fade-in.visible { opacity: 1; transform: none; }

/* ── Narrative ── */
.narrative-card {
  display: flex;
  gap: 1rem;
  background: var(--surface);
  border-radius: var(--radius);
  padding: 1.5rem;
  border: 1px solid var(--border);
}
.narrative-accent {
  flex-shrink: 0;
  width: 4px;
  background: var(--teal);
  border-radius: 4px;
}
.narrative-body { color: var(--text); line-height: 1.8; font-size: 0.97rem; }
.narrative-body h3 { color: var(--teal); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; margin: 1.1rem 0 0.3rem; }
.narrative-body h4 { color: var(--muted); font-size: 0.9rem; font-weight: 600; margin: 0.8rem 0 0.25rem; }
.narrative-body p { margin-bottom: 0.7rem; }
.narrative-body p:last-child { margin-bottom: 0; }
.narrative-body ul { padding-left: 1.4rem; margin-bottom: 0.7rem; }
.narrative-body li { margin-bottom: 0.2rem; }
.narrative-body ul:last-child { margin-bottom: 0; }

/* ── Stat cards ── */
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}
@media (max-width: 700px) { .card-grid { grid-template-columns: 1fr; } }
@media (min-width: 701px) and (max-width: 900px) { .card-grid { grid-template-columns: repeat(2, 1fr); } }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
}
.card--warn { background: var(--warn-dim); border-color: var(--warn); }
.card--alert { background: var(--alert-dim); border-color: var(--alert); }
.card-label { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted); margin-bottom: 0.4rem; }
.card-value { font-size: 2rem; font-weight: 700; color: var(--text); line-height: 1; margin-bottom: 0.5rem; }
.card--warn .card-value { color: var(--warn); }
.card--alert .card-value { color: var(--alert); }
.card-detail { font-size: 0.85rem; color: var(--muted); }

.prop-list { list-style: none; padding: 0; margin-top: 0.5rem; }
.prop-list li { font-size: 0.8rem; color: var(--muted); padding: 2px 0; }
.prop-list li::before { content: "• "; color: var(--teal); }
.empty { font-size: 0.82rem; color: var(--muted); font-style: italic; }

/* ── Charts ── */
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}
@media (max-width: 700px) { .charts-grid { grid-template-columns: 1fr; } }

.chart-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
}
.chart-title { font-size: 0.85rem; font-weight: 600; color: var(--muted); margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }

/* ── Tables ── */
.table-spacer { height: 1.5rem; }
.table-subtitle { font-size: 0.95rem; font-weight: 600; color: var(--text); margin: 1rem 0 0.5rem; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  white-space: nowrap;
}
.data-table th {
  background: var(--surface2);
  color: var(--muted);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  padding: 0.6rem 0.75rem;
  text-align: center;
  border-bottom: 1px solid var(--border);
}
.data-table th:first-child { text-align: left; }
.data-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
  text-align: center;
  color: var(--text);
}
.data-table td:first-child { text-align: left; }
.data-table tbody tr:hover { background: var(--surface2); }
.city-cell { font-weight: 500; color: var(--text); }
.today-col { background: var(--teal-dim) !important; color: var(--teal) !important; font-weight: 600; }
.total-row td { font-weight: 700; background: var(--surface2); border-top: 2px solid var(--border); }

/* ── Overdue table ── */
.overdue-table th { background: var(--alert-dim); color: var(--alert); }
.days-overdue { color: var(--alert); font-weight: 700; }
.task-link { color: var(--teal); text-decoration: none; font-size: 0.8rem; }
.task-link:hover { text-decoration: underline; }

/* ── Owner stays table ── */
.owner-table-wrap {
  border-left: 4px solid var(--owner);
  border-radius: var(--radius);
  overflow: hidden;
}
.owner-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
}
.owner-table th {
  background: var(--owner-dim);
  color: var(--owner);
  font-size: .75rem;
  text-transform: uppercase;
  letter-spacing: .05em;
  padding: .6rem 1rem;
  text-align: left;
}
.owner-table td { padding: .6rem 1rem; border-bottom: 1px solid var(--border); }
.owner-table tbody tr:last-child td { border-bottom: none; }
.owner-table tbody tr:hover { background: var(--surface2); }
.os-date { color: var(--owner); font-weight: 600; white-space: nowrap; width: 120px; }
.os-prop { color: var(--text); }
.os-empty { color: var(--muted); font-style: italic; text-align: center; padding: 1.25rem; }

/* ── Footer ── */
.site-footer {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--muted);
  font-size: 0.8rem;
  border-top: 1px solid var(--border);
  margin-top: 3rem;
}
"""
