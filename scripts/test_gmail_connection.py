"""Quick smoke test for Gmail API authentication and email listing.

Run from the project root:
    python scripts/test_gmail_connection.py
"""

import sys
import os

# Allow imports from src/ when running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gmail_client import authenticate


def main() -> None:
    print("Authenticating with Gmail API...")
    try:
        service = authenticate()
        print("Authentication successful.\n")
    except Exception as e:
        print(f"Authentication FAILED: {e}")
        sys.exit(1)

    print("Fetching 5 most recent emails...")
    try:
        results = service.users().messages().list(userId="me", maxResults=5).execute()
        messages = results.get("messages", [])
    except Exception as e:
        print(f"Failed to list messages: {e}")
        sys.exit(1)

    if not messages:
        print("No messages found in inbox.")
        sys.exit(0)

    for msg_ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata", metadataHeaders=["Subject", "From"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "(unknown sender)")
        print(f"  Subject: {subject}")
        print(f"  From:    {sender}")
        print()

    print("SUCCESS — Gmail connection working.")


if __name__ == "__main__":
    main()
