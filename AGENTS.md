# AGENTS.md — Agent Operating Manual

## What This Is
Python script that reads automated email reports from short-term rental (STR) management tools,
extracts key business metrics, and sends a formatted daily briefing email each morning.

Read CLAUDE.md for Claude Code-specific settings. This file is the canonical cross-tool briefing.

## Quick Start
1. Read this file and CLAUDE.md before doing anything.
2. Use `grep` or file search to locate relevant code — do not scan the entire repo.
3. Make small, testable changes.
4. Run verification commands before declaring completion.

## Repository Map
- `src/` — application code (parsers, KPI logic, email/dashboard generation, Gmail client)
- `tests/` — unit tests with sample data; never use live API calls in tests
- `scripts/` — dry-run and preview tools for local testing without sending email
- `docs/` — auto-generated HTML dashboard served via GitHub Pages
- `.github/workflows/` — GitHub Actions cron job (runs at 8:30 UTC = 4:30 AM EDT daily)

## Build, Run, Test
- Install dependencies: `pip install -r requirements.txt`
- Run tests: `python3 -m pytest tests/ -v`
- Preview dashboard (no Gmail needed): `python3 scripts/preview_dashboard.py`
- Dry-run full pipeline: `python3 scripts/send_test_email.py --dry-run`

## Definition of Done
A change is complete only if:
- The requested functionality is implemented
- `python3 -m pytest tests/ -v` passes
- `python3 scripts/send_test_email.py --dry-run` passes
- No secrets are added or exposed

## Architecture
Entry point: `src/main.py` — orchestrates the full pipeline:

```
fetch emails → parse → compute KPIs → classify stale tasks → generate narrative → build dashboard → send email
```

### Pipeline Steps (main.py)
- **a.** Gmail auth
- **b.** Fetch Guesty + Breezeway emails (48h window)
- **c.** Parse emails into reservation/task dicts
- **d.** `compute_kpis()` → structured KPI snapshot
- **d2.** `classify_stale_tasks()` → AI filters stale list to real issues only
- **e.** `generate_narrative()` → Claude writes morning briefing text
- **f.** `build_dashboard()` → saves docs/index.html
- **g.** `build_email_html()` → phone-friendly email
- **h.** `send_email()` → Gmail API

### Key Modules
- `src/gmail_client.py` — Gmail API auth and email fetch/send
- `src/parsers/guesty.py` — parses Guesty HTML email body into reservation dicts
- `src/parsers/breezeway.py` — parses Breezeway CSV attachment into task dicts
- `src/kpi.py` — aggregates parsed data into KPI snapshot
- `src/task_classifier.py` — Claude Haiku classifies stale tasks as issues vs. scheduled work
- `src/narrative.py` — generates morning briefing text via Claude sonnet-4-6
- `src/email_report.py` — builds phone-friendly HTML email
- `src/dashboard.py` — builds full HTML dashboard saved to docs/index.html

## Data Sources

### Guesty (HTML email body)
- Sender: noreply@guesty.com
- Columns: CHECK-IN, CHECK-OUT, LISTING, LISTING'S NICKNAME, LISTING'S CITY, CREATION DATE,
  PLATFORM, COMMISSION, TOTAL PAYOUT, ACCOMMODATION FARE, SOURCE, CHANNEL RESERVATION ID
- Date format: "YYYY-MM-DD HH:MM AM/PM"
- COMMISSION = our management fee — primary revenue metric. MTD filters by `creation_date`; YTD filters by `check_in`.
- SOURCE field: "owner" and "owner-guest" = no-revenue stays requiring special attention
- listing_name: prefers NICKNAME column; falls back to text before " / " in LISTING column

### Breezeway (CSV attachment)
- Sender: address contains "breezeway"
- Key columns: Task title, Property, Department, Subdepartment, Assignees, Due date, Status, Priority, Requested by
- Due date formats: M/DD/YY or YYYY-MM-DD (parser handles both)
- "Requested by: Guest" = guest-initiated task
- CSV is exported with a UTF-8 BOM (`\ufeff`) — parser strips it automatically via `csv_content.lstrip("\ufeff")`

### Price Labs
- Not yet implemented — placeholder only

## KPI Snapshot Structure (`compute_kpis()` output)
```python
{
  "today": {
      "checkins": [...], "checkouts": [...], "same_day_turns": [...],
      "inspections": [...], "owner_stays": [...],
      "overdue_tasks": [...], "high_priority_overdue": [...], "guest_requests_overdue": [...],
      "tasks_by_department": {...}, "total_estimated_hours_today": float,
  },
  "yesterday_bookings": {"new_commission": float, "new_reservation_count": int, "by_platform": {...}},
  "revenue": {
      "total_commission": float,   # sum of all reservations in Guesty export
      "mtd_commission": float,     # filtered by creation_date (booking date) this month
      "ytd_commission": float,     # filtered by check_in this year — total commission on the books for the calendar year
      "avg_commission_per_reservation": float,
      "commission_by_property": {...},  # top 10
      "commission_by_platform": {...},
  },
  "rolling_7_days": {
      "checkins_by_city": {day: {city: {"count": int, "properties": [str, ...]}}},
      "same_day_turns_by_city": {day: {city: int}},
      "inspections_by_city": {day: {city: {"count": int, "properties": [str, ...]}}},
  },
  "owner_stays_upcoming": [  # next 30 days, source in {"owner", "owner-guest"}
      {"listing_name": str, "city": str, "check_in": str, "check_out": str,
       "source": str, "days_until": int},
  ],
  "first_stays_of_year": [  # properties whose first guest check-in of the year is within 45 days
      {"listing_name": str, "city": str, "check_in": str, "days_until": int},
  ],
  "operations_detail": {
      "tasks_by_department_all": {...},
      "assignee_workload_7_days": {...},
      "stale_tasks": [...],  # post-processed by task_classifier.py — real issues only
  },
  "data_quality": {"guesty_available": bool, "breezeway_available": bool, ...},
}
```

## Overdue and Stale Task Filtering
- `_OVERDUE_DEPARTMENTS = {"Maintenance", "Inspection"}` in `src/kpi.py` — cleaning tasks excluded because cleaners don't reliably mark tasks complete
- **Stale tasks** are further filtered by `src/task_classifier.py` using Claude Haiku: scheduled/recurring tasks (Arrival Inspections, Hot Tub Services, Vacancy Inspections, Safety Inspections) are removed; only real ad-hoc issues (broken items, damage, guest complaints) remain
- Fallback keyword filter in `task_classifier._keyword_fallback()` runs if the API call fails

## Owner Stay Detection
- Determined by Guesty `source` field values: `"owner"` or `"owner-guest"`
- Constant: `_OWNER_SOURCES = {"owner", "owner-guest"}` in `src/kpi.py`
- `_compute_owner_stays_upcoming()` looks 30 days ahead
- Owner stays with `total_payout = $0` are expected — no revenue collected

## City Lookup for Breezeway Tasks
- Breezeway CSV lacks city data; city is cross-referenced from Guesty reservations
- `_build_property_city_lookup()` builds `{listing_name: city}` from Guesty data
- `_lookup_city()` uses exact match first, then prefix match to handle name truncation differences

## Narrative Tone Guidelines
The narrative prompt in `src/narrative.py` is intentionally factual and non-directive:
- **Do NOT** use: "urgent", "must", "immediately", "ASAP", "critical", "focus on X", "resolve before end of day"
- **Do** surface useful context: next check-in date at properties with open issues, whether a task was guest-initiated
- Let facts inform decisions — do not tell the team what to do or assign urgency

## First Stays of the Year
- `_compute_first_stays_of_year()` in `src/kpi.py` — 45-day lookahead
- For each property, finds the earliest guest check-in of the calendar year (excludes owner/owner-guest stays)
- If that first stay is upcoming (>= today, <= today + 45 days), surfaces it
- Properties whose first stay already happened are excluded
- Output: `{listing_name, city, check_in, days_until}` sorted by check_in
- Rendered in both dashboard and email report

## Dashboard Features
- Design: DM Sans + JetBrains Mono fonts, dark theme (#111318 bg), teal accent (#3db8c1), no emojis
- Operations-first layout: Today → 7-day rolling → workload → owner stays → season openers → charts → overdue → stale
- Check-ins by City and Arrival Inspections by City tables are expandable (click city row to reveal per-property grid)
- Expandable table JS uses `toggleCity(groupId)` with prefixes `"ci-"` (check-ins) and `"insp-"` (inspections) to avoid ID collisions
- Stat cards use 4-column grid on desktop, 2 on mobile; numbers in monospace font

## Coding Standards
- Type hints on all function signatures
- Docstrings on all public functions
- Use logging module, not print statements
- Config via environment variables or config.py — never hardcoded values
- Each parser returns a list of dicts with consistent keys
- Handle missing/malformed data gracefully: log warning, skip record, don't crash

## Safety and Secrets
- Never read, print, or commit credentials
- `.env` and `token.json` are gitignored — never touch them
- Use `.env.example` to document required variables

## Protected Files — Do Not Modify Unless Explicitly Asked
- `AGENTS.md`
- `CLAUDE.md`
- `.env`, `credentials.json`, `token.json`
- `.gitignore`
- `requirements.txt` (unless the task requires a new dependency)

## Common Mistakes to Avoid
- Gmail API email bodies are base64-encoded — always decode before parsing
- Guesty HTML may have inconsistent whitespace in table cells — strip all values
- Breezeway CSV may have empty rows or trailing commas — handle gracefully
- Breezeway CSV has a UTF-8 BOM — always strip with `csv_content.lstrip("\ufeff")` before parsing
- Property names differ between Guesty and Breezeway — use `_lookup_city()` prefix matching, do not exact-match
- Properties range from 8 (winter) to 50+ (summer) — never hardcode property lists
- MTD commission filters by `creation_date` (booking date) — tracks new revenue booked this month
- YTD commission filters by `check_in` (stay date) — total commission on the books for the calendar year

## Handoff Notes
**Last session (2026-03-23):**
- **Added**: `_compute_first_stays_of_year()` in `src/kpi.py` — 45-day lookahead for properties opening for the season
- **Added**: `_render_first_stays()` in `src/dashboard.py` and `src/email_report.py`
- **Added**: 6 new tests in `tests/test_kpi.py` for first stays (+ `source` param on `_make_reservation()`)
- **Redesigned**: Dashboard CSS — DM Sans + JetBrains Mono fonts, unified teal accent (removed purple), desaturated palette, left-aligned header, 4-col card grid, monospace numbers, removed all emojis
- **Tests**: 59 passed. Dry-run passed.
- **Committed and pushed**: `3669355 feat: first stays of year + dashboard redesign`
- **Still unstaged from prior sessions**: spending_guard.py, config.py, gmail_client.py, main.py, narrative.py, task_classifier.py, workflow, gitignore changes
