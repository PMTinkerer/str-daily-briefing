"""Configuration loaded from environment variables."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

GMAIL_CREDENTIALS_PATH: str = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
GMAIL_TOKEN_PATH: str = os.getenv("GMAIL_TOKEN_PATH", "token.json")

BRIEFING_RECIPIENTS: list[str] = [
    addr.strip()
    for addr in os.getenv("BRIEFING_RECIPIENTS", "").split(",")
    if addr.strip()
]

REPORT_SENDER_GUESTY: str = os.getenv("REPORT_SENDER_GUESTY", "noreply@guesty.com")
REPORT_SENDER_BREEZEWAY: str = os.getenv("REPORT_SENDER_BREEZEWAY", "breezeway")

DASHBOARD_URL: str = os.getenv(
    "DASHBOARD_URL",
    "https://pmtinkerer.github.io/str-daily-briefing/",
)
