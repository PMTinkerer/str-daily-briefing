"""Fetch the most recent Breezeway email and save the CSV attachment for testing.

Falls back to writing a manual 3-row sample if no email is found.

Run from the project root:
    python3 scripts/fetch_breezeway_sample.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gmail_client import authenticate, fetch_recent_emails

SAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "sample_data", "breezeway_sample.csv",
)

MANUAL_SAMPLE = """\
Task title,Property,Property tags,Due date,Status,Estimated time,Created date,Task report link,Property Time Zone
"Arrival Inspection - L (w/ Inventory)","Sandpiper by the Sea - 18 School Street","Breezeway Cleaning; Luxe; Sandpiper - Main House; Ogunquit","9/15/25","Created","1:00:00","7/31/25","https://portal.breezeway.io/task/report/5005ca71-5d79-4b2b-931d-f109b8ac9b14","(UTC-05:00) Eastern Time (US & Canada)"
"Arrival Inspection - M (w/ Inventory)","Harborview + Playhouse - 10 Harbor View Lane","Breezeway Cleaning; Mid; York","9/2/25","Created","0:45:00","7/31/25","https://portal.breezeway.io/task/report/40627057-c2ca-4ea1-97fe-138eff2685e6","(UTC-05:00) Eastern Time (US & Canada)"
"Breezeway Assist Escalation- Late check out request","Cape Neddick Coastal Hideaway - 33 Old County Road","Breezeway Cleaning; Mid; York","8/1/25","Overdue","","8/1/25","https://portal.breezeway.io/task/report/769951ef-4fe7-4016-8ec8-95ab759c80e2","(UTC-05:00) Eastern Time (US & Canada)"
"""


def main() -> None:
    os.makedirs(os.path.dirname(SAMPLE_PATH), exist_ok=True)

    print("Authenticating with Gmail API...")
    try:
        service = authenticate()
        print("Authenticated.\n")
    except Exception as e:
        print(f"Authentication failed: {e}")
        print("Writing manual sample instead...")
        _write_manual_sample()
        return

    print("Fetching Breezeway emails from the last 7 days...")
    emails = fetch_recent_emails(service, sender_filter="breezeway", hours_back=168)

    if not emails:
        print("No Breezeway emails found. Writing manual sample...")
        _write_manual_sample()
        return

    # Find the first email that has a CSV attachment
    for email in emails:
        csv_attachments = [
            a for a in email["attachments"]
            if a["filename"].lower().endswith(".csv")
        ]
        if csv_attachments:
            att = csv_attachments[0]
            print(f"Found CSV attachment: {att['filename']!r}")
            print(f"  From email: {email['subject']} ({email['date']})")
            with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
                f.write(att["content"])
            print(f"Saved to: {SAMPLE_PATH}")
            print("You can now run: python3 -m pytest tests/test_breezeway_parser.py -v")
            return

    print("Emails found but none had a CSV attachment. Writing manual sample...")
    _write_manual_sample()


def _write_manual_sample() -> None:
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        f.write(MANUAL_SAMPLE)
    print(f"Manual sample written to: {SAMPLE_PATH}")
    print("You can now run: python3 -m pytest tests/test_breezeway_parser.py -v")


if __name__ == "__main__":
    main()
