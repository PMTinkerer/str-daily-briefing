"""Live end-to-end test: fetch Guesty email and print parsed reservation summary.

Run from the project root:
    python scripts/test_guesty_fetch.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gmail_client import authenticate, fetch_recent_emails
from src.parsers.guesty import parse_guesty_report


def main() -> None:
    print("Authenticating with Gmail API...")
    service = authenticate()
    print("Authenticated.\n")

    print("Fetching Guesty emails from the last 7 days...")
    emails = fetch_recent_emails(service, sender_filter="noreply@guesty.com", hours_back=168)

    if not emails:
        print("No Guesty emails found in the last 7 days.")
        sys.exit(1)

    email = emails[0]
    print(f"Using email: {email['subject']} ({email['date']})")
    print(f"HTML body: {len(email['body_html'])} chars\n")

    if not email["body_html"]:
        print("ERROR: Email has no HTML body.")
        sys.exit(1)

    reservations = parse_guesty_report(email["body_html"])

    if not reservations:
        print("WARNING: Parser returned 0 reservations. Check the HTML structure.")
        sys.exit(1)

    check_ins = [r["check_in"] for r in reservations]
    check_outs = [r["check_out"] for r in reservations]
    total_commission = sum(r["commission"] for r in reservations)
    unique_properties = len({r["listing_name"] for r in reservations})

    print("=" * 50)
    print(f"Total reservations:   {len(reservations)}")
    print(f"Date range:           {min(check_ins)} → {max(check_outs)}")
    print(f"Total commission:     ${total_commission:,.2f}")
    print(f"Unique properties:    {unique_properties}")
    print("=" * 50)
    print("\nSUCCESS")


if __name__ == "__main__":
    main()
