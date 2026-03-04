"""Fetch the most recent Guesty email and save the HTML body for testing.

Run from the project root:
    python scripts/fetch_guesty_sample.py

Requires valid Gmail credentials (token.json or credentials.json).
Saves to tests/sample_data/guesty_sample.html.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gmail_client import authenticate, fetch_recent_emails

SAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "sample_data", "guesty_sample.html",
)


def main() -> None:
    print("Authenticating with Gmail API...")
    service = authenticate()
    print("Authenticated.\n")

    print("Fetching Guesty emails from the last 7 days...")
    emails = fetch_recent_emails(service, sender_filter="noreply@guesty.com", hours_back=168)

    if not emails:
        print("WARNING: No Guesty emails found in the last 7 days.")
        print("Try expanding the search window or check the sender address.")
        sys.exit(1)

    email = emails[0]
    print(f"Found {len(emails)} email(s). Using most recent:")
    print(f"  Subject: {email['subject']}")
    print(f"  Date:    {email['date']}")
    print(f"  Body:    {len(email['body_html'])} chars\n")

    if not email["body_html"]:
        print("ERROR: Email has no HTML body. Cannot save sample.")
        sys.exit(1)

    os.makedirs(os.path.dirname(SAMPLE_PATH), exist_ok=True)
    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        f.write(email["body_html"])

    print(f"Saved HTML body to: {SAMPLE_PATH}")
    print("You can now run: python -m pytest tests/test_guesty_parser.py -v")


if __name__ == "__main__":
    main()
