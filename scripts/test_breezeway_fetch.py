"""Live end-to-end test: fetch Breezeway email and print parsed task summary.

Run from the project root:
    python3 scripts/test_breezeway_fetch.py
"""

import os
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gmail_client import authenticate, fetch_recent_emails
from src.parsers.breezeway import parse_breezeway_report


def main() -> None:
    print("Authenticating with Gmail API...")
    service = authenticate()
    print("Authenticated.\n")

    print("Fetching Breezeway emails from the last 7 days...")
    emails = fetch_recent_emails(service, sender_filter="breezeway", hours_back=168)

    if not emails:
        print("No Breezeway emails found in the last 7 days.")
        sys.exit(1)

    # Find first email with a CSV attachment
    csv_content = None
    source_email = None
    for email in emails:
        for att in email["attachments"]:
            if att["filename"].lower().endswith(".csv"):
                csv_content = att["content"]
                source_email = email
                break
        if csv_content:
            break

    if not csv_content:
        print("Emails found but none had a CSV attachment.")
        sys.exit(1)

    print(f"Using email: {source_email['subject']} ({source_email['date']})\n")

    tasks = parse_breezeway_report(csv_content)

    if not tasks:
        print("WARNING: Parser returned 0 tasks. Check the CSV structure.")
        sys.exit(1)

    today = date.today().strftime("%Y-%m-%d")
    status_counts = Counter(t["status"] for t in tasks)
    due_today = [t for t in tasks if t["due_date"] == today]
    overdue = [t for t in tasks if t["status"].lower() == "overdue"]

    print("=" * 50)
    print(f"Total tasks:     {len(tasks)}")
    print()
    print("By status:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<20} {count}")
    print()
    print(f"Due today:       {len(due_today)}")
    print(f"Overdue:         {len(overdue)}")
    print("=" * 50)
    print("\nSUCCESS")


if __name__ == "__main__":
    main()
