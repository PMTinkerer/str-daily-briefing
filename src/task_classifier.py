"""Classify Breezeway stale tasks as real issues vs. scheduled work via Claude Haiku."""

from __future__ import annotations

import json
import logging

import anthropic

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"

# Fallback keyword filter used if the API call fails
_SCHEDULED_KEYWORDS: frozenset[str] = frozenset({
    "Arrival Inspection",
    "Hottub Service",
    "Hot Tub Service",
    "Vacancy Inspection",
    "Safety Inspection",
    "Bring Trash",
})

_SYSTEM = (
    "You classify property maintenance tasks for a short-term rental management company. "
    "For each task, decide if it is a real 'issue' (ad-hoc problem: broken item, damage, "
    "guest complaint, equipment failure) or 'scheduled' (routine/recurring work: inspections, "
    "hot tub service, safety checks, vacancy checks, trash day, periodic cleaning). "
    "Return JSON with key 'issue_indices' listing the 0-based indices of tasks that are issues."
)


def classify_stale_tasks(tasks: list[dict], api_key: str) -> list[dict]:
    """Filter stale tasks to only real issues using Claude Haiku.

    Args:
        tasks: List of stale task dicts from compute_kpis().
        api_key: Anthropic API key.

    Returns:
        Filtered list containing only ad-hoc issue tasks.
        Falls back to keyword filtering if the API call fails.
    """
    if not tasks:
        return tasks

    task_summaries = [
        {
            "index": i,
            "title": t.get("task_title", ""),
            "department": t.get("department", ""),
            "requested_by": t.get("requested_by", ""),
            "priority": t.get("priority", ""),
        }
        for i, t in enumerate(tasks)
    ]

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_MODEL,
            max_tokens=256,
            system=_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(task_summaries)}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "issue_indices": {
                                "type": "array",
                                "items": {"type": "integer"},
                            }
                        },
                        "required": ["issue_indices"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        result = json.loads(response.content[0].text)
        issue_indices = set(result.get("issue_indices", []))
        filtered = [t for i, t in enumerate(tasks) if i in issue_indices]
        logger.info(
            "Task classifier: %d stale candidates → %d issues kept",
            len(tasks),
            len(filtered),
        )
        return filtered

    except Exception:
        logger.warning(
            "Stale task classification API call failed — using keyword fallback",
            exc_info=True,
        )
        return _keyword_fallback(tasks)


def _keyword_fallback(tasks: list[dict]) -> list[dict]:
    """Return tasks that don't match any known scheduled-task keyword.

    Args:
        tasks: List of task dicts.

    Returns:
        Filtered list with scheduled tasks removed.
    """
    return [
        t for t in tasks
        if not any(kw in t.get("task_title", "") for kw in _SCHEDULED_KEYWORDS)
    ]
