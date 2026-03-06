# STR Daily Briefing — KPI Dashboard

## What This Is
Python script that reads automated email reports from short-term rental (STR) management tools,
extracts key business metrics, and sends a formatted daily briefing email each morning.

## Tech Stack
- Python 3.12+
- Gmail API (google-api-python-client, google-auth-oauthlib) for reading and sending email
- BeautifulSoup4 for parsing HTML email bodies (Guesty reports)
- csv module (stdlib) for parsing CSV attachments (Breezeway reports)
- GitHub Actions for scheduled daily execution at 4:30 AM ET

## Project Structure
```
str-daily-briefing/
├── CLAUDE.md
├── AGENTS.md
├── README.md
├── requirements.txt
├── .github/
│   └── workflows/
│       └── daily-briefing.yml
├── src/
│   ├── __init__.py
│   ├── main.py              # Orchestrator: fetch → parse → compute → narrate → dashboard → send
│   ├── gmail_client.py      # Gmail API auth, fetch emails, send emails
│   ├── email_report.py      # Build compact inline-HTML email summary (phone-friendly)
│   ├── dashboard.py         # Build full self-contained HTML dashboard (saved to docs/)
│   ├── narrative.py         # Generate morning briefing narrative via Claude API
│   ├── kpi.py               # Aggregate parsed data into KPI snapshot
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── guesty.py        # Parse Guesty HTML email into reservation dicts
│   │   └── breezeway.py     # Parse Breezeway CSV attachment into task dicts
│   ├── report.py            # Stub — superseded by email_report.py + dashboard.py
│   └── config.py            # Sender addresses, recipient list, dashboard URL, report settings
├── scripts/
│   ├── preview_dashboard.py # Build dashboard from sample data (no Gmail needed)
│   └── send_test_email.py   # Dry-run full pipeline with confirmation before sending
├── docs/
│   └── index.html           # Auto-generated dashboard (served via GitHub Pages)
├── tests/
│   ├── test_guesty_parser.py
│   ├── test_breezeway_parser.py
│   ├── test_kpi.py
│   └── sample_data/         # Sample email bodies and CSV files for testing
├── .env.example
└── .gitignore
```

## Data Sources

### Guesty (email body — HTML table)
- Sender: noreply@guesty.com
- Subject pattern: contains "Guesty" and "report"
- Format: HTML table in email body with columns:
  CHECK-IN, CHECKOUT, LISTING, LISTING'S CITY, CREATION DATE, PLATFORM, COMMISSION
- Dates are in "YYYY-MM-DD HH:MM AM/PM" format
- COMMISSION is a float (dollar amount). This may expand to include revenue columns later.
- Listing names contain " / " separator between short name and description

### Breezeway (CSV attachment)
- Sender: contains "breezeway" in from address
- Format: CSV file attached to email
- Columns: Task title, Property, Department, Subdepartment, Assignees, Due date, Status,
  Priority, Bill to, Requested by, Estimated time, Created date, Created by,
  Last updated date, Task report link, Property Time Zone
- Due date formats: M/DD/YY or YYYY-MM-DD (parser handles both)
- Property may optionally have a "Property tags" column (semicolon-separated: cleaning company; tier; property name; city)
- Status values include: Created, Overdue (expect others)
- "Requested by: Guest" indicates a guest-initiated task

### Price Labs (FUTURE — not yet implemented)
- Placeholder parser exists but is not active
- Will be added as src/parsers/pricelabs.py when ready

## Coding Standards
- Type hints on all function signatures
- Docstrings on all public functions (one-line summary + args/returns)
- Use logging module, not print statements
- All config via environment variables or config.py, never hardcoded
- Each parser returns a list of dicts with consistent keys
- Handle missing/malformed data gracefully — log warning, skip record, don't crash
- IMPORTANT: Never commit credentials. .env and token files are in .gitignore.

## Testing
- Run tests: `python -m pytest tests/ -v`
- Each parser has a test file with sample data
- Tests use sample data files in tests/sample_data/, not live API calls

## Before Saying You're Done
Run these after every change. Do not declare completion until they pass:
- `python -m pytest tests/ -v`
- `python scripts/send_test_email.py --dry-run`

If either command fails, fix it in the same session before stopping.

## Gmail Client

### `authenticate() -> Resource`
Loads `token.json` if present, refreshes if expired, runs OAuth browser flow otherwise.
Config: `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`.
**Scope change note:** Adding a new scope (e.g. `gmail.send`) requires deleting `token.json`
and re-running to trigger re-consent.

### `fetch_recent_emails(service, sender_filter, hours_back=24) -> list[dict]`
Returns list of dicts: `id`, `subject`, `from`, `date`, `body_html`, `attachments`.
Each attachment: `{filename: str, content: str}`.

### `send_email(service, to, subject, html_body) -> bool`
Sends HTML email from the authenticated account (`me`).
Returns `True` on success, `False` on failure (logs error, does not raise).
Requires `gmail.send` scope.

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| `GMAIL_CREDENTIALS_PATH` | `credentials.json` | OAuth client credentials file |
| `GMAIL_TOKEN_PATH` | `token.json` | Saved OAuth token (gitignored) |
| `BRIEFING_RECIPIENTS` | _(empty)_ | Comma-separated recipient addresses |
| `REPORT_SENDER_GUESTY` | `noreply@guesty.com` | Guesty sender filter |
| `REPORT_SENDER_BREEZEWAY` | `breezeway` | Breezeway sender filter |
| `DASHBOARD_URL` | GitHub Pages URL | Full dashboard link (used in email CTA) |
| `ANTHROPIC_API_KEY` | _(required)_ | Claude API key for narrative generation |
| `REPORT_DATE` | today | Override report date (YYYY-MM-DD) |

## Common Mistakes to Avoid
- Gmail API email bodies are base64-encoded — always decode before parsing
- Guesty HTML may have inconsistent whitespace in table cells — strip all values
- Breezeway CSV may have empty rows or trailing commas — handle gracefully
- Property names differ slightly between Guesty and Breezeway — don't try to match them in v1
- The number of properties changes seasonally (8 in winter, 50+ in summer) — never hardcode property lists
