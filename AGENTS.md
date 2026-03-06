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
- `.github/workflows/` — GitHub Actions cron job (runs at 4:30 AM ET daily)

## Build, Run, Test
- Install dependencies: `pip install -r requirements.txt`
- Run tests: `python -m pytest tests/ -v`
- Preview dashboard (no Gmail needed): `python scripts/preview_dashboard.py`
- Dry-run full pipeline: `python scripts/send_test_email.py --dry-run`

## Definition of Done
A change is complete only if:
- The requested functionality is implemented
- `python -m pytest tests/ -v` passes
- `python scripts/send_test_email.py --dry-run` passes
- No secrets are added or exposed

## Architecture
Entry point: `src/main.py` — orchestrates the full pipeline: fetch → parse → compute → narrate → dashboard → send

Key modules:
- `src/gmail_client.py` — Gmail API auth and email fetch/send
- `src/parsers/guesty.py` — parses Guesty HTML email body into reservation dicts
- `src/parsers/breezeway.py` — parses Breezeway CSV attachment into task dicts
- `src/kpi.py` — aggregates parsed data into KPI snapshot
- `src/narrative.py` — generates morning briefing text via Claude API
- `src/email_report.py` — builds phone-friendly HTML email
- `src/dashboard.py` — builds full HTML dashboard saved to docs/index.html

## Data Sources

### Guesty (HTML email body)
- Sender: noreply@guesty.com
- Columns: CHECK-IN, CHECKOUT, LISTING, LISTING'S CITY, CREATION DATE, PLATFORM, COMMISSION
- Date format: "YYYY-MM-DD HH:MM AM/PM"
- COMMISSION is a dollar float — not total revenue

### Breezeway (CSV attachment)
- Sender: address contains "breezeway"
- Key columns: Task title, Property, Department, Assignees, Due date, Status, Priority, Requested by
- Due date formats: M/DD/YY or YYYY-MM-DD (parser handles both)
- "Requested by: Guest" = guest-initiated task
- CSV is exported with a UTF-8 BOM (`\ufeff`) — parser strips it automatically via `csv_content.lstrip("\ufeff")`

### Price Labs
- Not yet implemented — placeholder only

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

## Overdue and Stale Task Filtering
Overdue and stale tasks are intentionally filtered to **Maintenance and Inspection departments only**.
Cleaning tasks accumulate as overdue because cleaners don't reliably mark them complete.
The constant `_OVERDUE_DEPARTMENTS = {"Maintenance", "Inspection"}` in `src/kpi.py` controls this.
`high_priority_overdue`, `guest_requests_overdue`, and `stale_tasks` all inherit this filter.

## Narrative Date Context
`src/narrative.py` prepends `"Today is {date} ({weekday}). Tomorrow is {tomorrow}."` before the KPI JSON
so the Claude API uses actual dates (e.g., "Friday, March 6") rather than relative terms like "tomorrow."

## Common Mistakes to Avoid
- Gmail API email bodies are base64-encoded — always decode before parsing
- Guesty HTML may have inconsistent whitespace in table cells — strip all values
- Breezeway CSV may have empty rows or trailing commas — handle gracefully
- Breezeway CSV has a UTF-8 BOM — always strip with `csv_content.lstrip("\ufeff")` before parsing
- Property names differ between Guesty and Breezeway — do not try to match them
- Properties range from 8 (winter) to 50+ (summer) — never hardcode property lists

## Handoff Notes
When stopping or switching tools, note here:
- What you changed (files + intent)
- Commands run and results
- What remains / next steps
