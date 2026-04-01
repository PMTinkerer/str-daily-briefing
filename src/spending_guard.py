"""Lightweight API spending guard with monthly budget enforcement.

Tracks per-call costs in a JSON ledger and enforces a configurable monthly cap.
When the budget is exhausted, callers should use their existing fallback paths.
Provider-agnostic — any API can call can_spend() / record_spend().
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Per-token pricing (USD).  Add new models / providers here.
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-haiku-4-5": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
}

# Conservative fallback for unknown models so they're safely budgeted.
DEFAULT_PRICING: dict[str, float] = {"input": 5.00 / 1_000_000, "output": 25.00 / 1_000_000}


def _current_month() -> str:
    """Return the current month as YYYY-MM."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def load_ledger(path: Path) -> dict:
    """Load the spend ledger from disk, resetting if the month rolled over.

    Args:
        path: Path to the JSON ledger file.

    Returns:
        Ledger dict with keys 'month' and 'entries'.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("month") == _current_month():
            return data
        logger.info("Spend ledger month rolled over — starting fresh")
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read spend ledger (%s) — starting fresh", exc)
    return {"month": _current_month(), "entries": []}


def save_ledger(ledger: dict, path: Path) -> None:
    """Persist the spend ledger to disk.

    Args:
        ledger: Ledger dict to save.
        path: Destination file path.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not save spend ledger: %s", exc)


def monthly_total(ledger: dict) -> float:
    """Sum all recorded costs for the current month.

    Args:
        ledger: Ledger dict.

    Returns:
        Total spend in USD.
    """
    return sum(e.get("cost_usd", 0.0) for e in ledger.get("entries", []))


def can_spend(ledger: dict, budget: float, estimated_cost: float = 0.15,
              warn_threshold: float = 0.80) -> bool:
    """Check whether the estimated cost fits within the remaining budget.

    Args:
        ledger: Current ledger dict.
        budget: Monthly budget cap in USD.
        estimated_cost: Estimated cost of the upcoming API call.
        warn_threshold: Fraction of budget at which to log a warning.

    Returns:
        True if the call should proceed, False if budget is exhausted.
    """
    total = monthly_total(ledger)
    if total >= budget:
        logger.warning("Monthly API budget exhausted ($%.2f / $%.2f)", total, budget)
        return False
    if total + estimated_cost > budget:
        logger.warning("Monthly API budget would be exceeded ($%.2f + ~$%.2f > $%.2f)",
                       total, estimated_cost, budget)
        return False
    if budget > 0 and total / budget >= warn_threshold:
        logger.warning("Monthly API spend at %.0f%% of budget ($%.2f / $%.2f)",
                       (total / budget) * 100, total, budget)
    return True


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the USD cost for a given API call.

    Args:
        model: Model identifier (e.g. 'claude-sonnet-4-5').
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.

    Returns:
        Cost in USD.
    """
    pricing = PRICING.get(model)
    if pricing is None:
        logger.warning("No pricing for model '%s' — using conservative default", model)
        pricing = DEFAULT_PRICING
    return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])


def record_spend(ledger: dict, provider: str, model: str,
                 input_tokens: int, output_tokens: int, caller: str,
                 override_cost: float | None = None) -> float:
    """Record an API call's cost in the ledger.

    Args:
        ledger: Ledger dict (mutated in place).
        provider: API provider name (e.g. 'anthropic').
        model: Model identifier.
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens produced.
        caller: Logical caller name for debugging (e.g. 'narrative').
        override_cost: If set, use this cost instead of computing from tokens.
            Useful for non-token-based APIs.

    Returns:
        The recorded cost in USD.
    """
    cost = override_cost if override_cost is not None else compute_cost(model, input_tokens, output_tokens)
    ledger.setdefault("entries", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "caller": caller,
    })
    return cost
