"""Tests for src/task_classifier.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.task_classifier import classify_stale_tasks, _keyword_fallback

# ── sample tasks ─────────────────────────────────────────────────────────────

ISSUE_TASK = {
    "task_title": "Broken doorknob",
    "department": "Maintenance",
    "requested_by": "",
    "priority": "Medium",
}

GUEST_ISSUE_TASK = {
    "task_title": "Deck slider door won't lock",
    "department": "Maintenance",
    "requested_by": "Guest",
    "priority": "High",
}

HOT_TUB_TASK = {
    "task_title": "Hottub Service - Guest Checkout",
    "department": "Maintenance",
    "requested_by": "",
    "priority": "Medium",
}

ARRIVAL_INSP_TASK = {
    "task_title": "Arrival Inspection - L (w/ Inventory)",
    "department": "Inspection",
    "requested_by": "",
    "priority": "Medium",
}

VACANCY_INSP_TASK = {
    "task_title": "30-Day Vacancy Inspection - Winter/Offseason",
    "department": "Inspection",
    "requested_by": "",
    "priority": "Low",
}

ALL_TASKS = [ISSUE_TASK, GUEST_ISSUE_TASK, HOT_TUB_TASK, ARRIVAL_INSP_TASK, VACANCY_INSP_TASK]


# ── keyword fallback tests ────────────────────────────────────────────────────

def test_keyword_fallback_keeps_issues():
    result = _keyword_fallback(ALL_TASKS)
    titles = [t["task_title"] for t in result]
    assert "Broken doorknob" in titles
    assert "Deck slider door won't lock" in titles


def test_keyword_fallback_removes_scheduled():
    result = _keyword_fallback(ALL_TASKS)
    titles = [t["task_title"] for t in result]
    assert "Hottub Service - Guest Checkout" not in titles
    assert "Arrival Inspection - L (w/ Inventory)" not in titles
    assert "30-Day Vacancy Inspection - Winter/Offseason" not in titles


def test_keyword_fallback_empty():
    assert _keyword_fallback([]) == []


# ── classify_stale_tasks: API path ────────────────────────────────────────────

def _make_api_response(issue_indices: list[int]) -> MagicMock:
    """Build a mock Anthropic response returning the given issue indices."""
    import json
    content_block = MagicMock()
    content_block.text = json.dumps({"issue_indices": issue_indices})
    response = MagicMock()
    response.content = [content_block]
    return response


def test_classify_uses_api_result():
    with patch("src.task_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        # API says indices 0 and 1 are issues (the two broken-thing tasks)
        mock_client.messages.create.return_value = _make_api_response([0, 1])

        result = classify_stale_tasks(ALL_TASKS, api_key="test-key")

    assert len(result) == 2
    assert result[0]["task_title"] == "Broken doorknob"
    assert result[1]["task_title"] == "Deck slider door won't lock"


def test_classify_empty_returns_empty():
    result = classify_stale_tasks([], api_key="test-key")
    assert result == []


def test_classify_falls_back_on_api_error():
    with patch("src.task_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API down")

        result = classify_stale_tasks(ALL_TASKS, api_key="test-key")

    # Should return keyword-filtered results, not crash
    titles = [t["task_title"] for t in result]
    assert "Broken doorknob" in titles
    assert "Hottub Service - Guest Checkout" not in titles
