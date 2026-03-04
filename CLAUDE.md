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
├── README.md
├── requirements.txt
├── .github/
│   └── workflows/
│       └── daily-briefing.yml
├── src/
│   ├── __init__.py
│   ├── main.py              # Orchestrator: fetch → parse → format → send
│   ├── gmail_client.py      # Gmail API auth, fetch emails, send emails
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── guesty.py        # Parse Guesty HTML email into reservation dicts
│   │   └── breezeway.py     # Parse Breezeway CSV attachment into task dicts
│   ├── report.py            # Generate HTML briefing email from parsed data
│   └── config.py            # Sender addresses, recipient list, report settings
├── tests/
│   ├── test_guesty_parser.py
│   ├── test_breezeway_parser.py
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
- Columns: Task title, Property, Property tags, Due date, Status,
  Estimated time, Created date, Task report link, Property Time Zone
- Due date format: M/DD/YY
- Property tags are semicolon-separated: cleaning company; tier; property name; city
- Status values include: Created, Overdue (expect others)
- Task title contains tier indicator: L=Luxe, M=Mid, E=Economy

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

## Common Mistakes to Avoid
- Gmail API email bodies are base64-encoded — always decode before parsing
- Guesty HTML may have inconsistent whitespace in table cells — strip all values
- Breezeway CSV may have empty rows or trailing commas — handle gracefully
- Property names differ slightly between Guesty and Breezeway — don't try to match them in v1
- The number of properties changes seasonally (8 in winter, 50+ in summer) — never hardcode property lists
