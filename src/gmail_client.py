"""Gmail API authentication and email fetching utilities."""

import base64
import logging
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def authenticate() -> Resource:
    """Authenticate with Gmail API and return a service object.

    Loads saved credentials from token file if available. Refreshes expired
    credentials automatically. Runs the OAuth browser flow for first-time auth
    and saves the resulting token for future use.

    Returns:
        Authenticated Gmail API service (googleapiclient Resource).
    """
    credentials_path = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "token.json")

    creds: Credentials | None = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        logger.debug("Loaded credentials from %s", token_path)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Gmail credentials")
            creds.refresh(Request())
        else:
            logger.info("Starting OAuth flow — browser will open")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
        logger.info("Saved credentials to %s", token_path)

    service = build("gmail", "v1", credentials=creds)
    logger.info("Gmail API authenticated successfully")
    return service


def fetch_recent_emails(
    service: Resource,
    sender_filter: str,
    hours_back: int = 24,
) -> list[dict]:
    """Fetch recent emails from a specific sender within the last N hours.

    Args:
        service: Authenticated Gmail API service object.
        sender_filter: Sender address or domain fragment to filter by (e.g. "noreply@guesty.com").
        hours_back: How many hours back to search. Defaults to 24.

    Returns:
        List of dicts, each with keys:
            id (str), subject (str), from (str), date (str),
            body_html (str), attachments (list of {filename, content}).
    """
    cutoff_ts = int(time.time()) - (hours_back * 3600)
    query = f"from:{sender_filter} after:{cutoff_ts}"
    logger.info("Searching Gmail: %s", query)

    results = (
        service.users()
        .messages()
        .list(userId="me", q=query)
        .execute()
    )
    messages = results.get("messages", [])
    logger.info("Found %d message(s) matching query", len(messages))

    emails: list[dict] = []
    for msg_ref in messages:
        try:
            email = _fetch_and_parse_message(service, msg_ref["id"])
            emails.append(email)
        except Exception:
            logger.warning("Failed to fetch message id=%s", msg_ref["id"], exc_info=True)

    return emails


def _fetch_and_parse_message(service: Resource, message_id: str) -> dict:
    """Fetch a single Gmail message and parse its headers, body, and attachments.

    Args:
        service: Authenticated Gmail API service object.
        message_id: Gmail message ID string.

    Returns:
        Dict with keys: id, subject, from, date, body_html, attachments.
    """
    raw = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    headers = {h["name"]: h["value"] for h in raw.get("payload", {}).get("headers", [])}

    body_html_ref: list[str] = [""]
    attachments: list[dict] = []
    _walk_parts(service, message_id, raw.get("payload", {}), body_html_ref=body_html_ref, attachments=attachments)
    body_html = body_html_ref[0]

    return {
        "id": message_id,
        "subject": headers.get("Subject", ""),
        "from": headers.get("From", ""),
        "date": headers.get("Date", ""),
        "body_html": body_html,
        "attachments": attachments,
    }


def _walk_parts(
    service: Resource,
    message_id: str,
    part: dict,
    body_html_ref: list[str],
    attachments: list[dict],
) -> None:
    """Recursively walk MIME parts to extract HTML body and attachments.

    Args:
        service: Authenticated Gmail API service object.
        message_id: Gmail message ID (needed to fetch attachment data).
        part: A MIME part dict from the Gmail API payload.
        body_html_ref: Single-element list used as a mutable reference for the HTML body.
        attachments: List to append attachment dicts to.
    """
    mime_type = part.get("mimeType", "")
    filename = part.get("filename", "")
    body = part.get("body", {})

    if mime_type == "text/html" and not filename:
        data = body.get("data", "")
        if data:
            body_html_ref[0] = _decode_base64(data)
            logger.debug("Extracted HTML body (%d chars)", len(body_html_ref[0]))

    elif filename:
        attachment_id = body.get("attachmentId")
        if attachment_id:
            try:
                att = (
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=message_id, id=attachment_id)
                    .execute()
                )
                content = _decode_base64(att.get("data", ""))
            except Exception:
                logger.warning(
                    "Failed to fetch attachment '%s' from message %s",
                    filename,
                    message_id,
                    exc_info=True,
                )
                content = ""
        else:
            data = body.get("data", "")
            content = _decode_base64(data) if data else ""

        attachments.append({"filename": filename, "content": content})
        logger.debug("Extracted attachment '%s' (%d bytes)", filename, len(content))

    for sub_part in part.get("parts", []):
        _walk_parts(service, message_id, sub_part, body_html_ref, attachments)


def _decode_base64(data: str) -> str:
    """Decode a URL-safe base64 string to a UTF-8 string.

    Args:
        data: Base64url-encoded string (Gmail API format).

    Returns:
        Decoded UTF-8 string. Returns empty string on decode failure.
    """
    try:
        # Pad to a multiple of 4 chars to avoid padding errors
        padded = data + "=" * (4 - len(data) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except Exception:
        logger.warning("Failed to base64-decode data (length=%d)", len(data), exc_info=True)
        return ""
