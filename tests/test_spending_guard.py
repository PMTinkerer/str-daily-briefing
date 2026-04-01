"""Tests for the spending guard module."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from src.spending_guard import (
    can_spend,
    compute_cost,
    load_ledger,
    monthly_total,
    record_spend,
    save_ledger,
)


class TestLoadLedger:
    def test_fresh_ledger_on_missing_file(self, tmp_path: Path) -> None:
        ledger = load_ledger(tmp_path / "missing.json")
        assert ledger["entries"] == []
        assert len(ledger["month"]) == 7  # YYYY-MM

    def test_loads_existing_ledger(self, tmp_path: Path) -> None:
        from src.spending_guard import _current_month
        path = tmp_path / "spend.json"
        data = {"month": _current_month(), "entries": [{"cost_usd": 0.05}]}
        path.write_text(json.dumps(data))
        ledger = load_ledger(path)
        assert len(ledger["entries"]) == 1

    def test_month_rollover_resets(self, tmp_path: Path) -> None:
        path = tmp_path / "spend.json"
        data = {"month": "1999-01", "entries": [{"cost_usd": 99.0}]}
        path.write_text(json.dumps(data))
        ledger = load_ledger(path)
        assert ledger["entries"] == []

    def test_corrupted_file_resets(self, tmp_path: Path) -> None:
        path = tmp_path / "spend.json"
        path.write_text("not json!!!")
        ledger = load_ledger(path)
        assert ledger["entries"] == []


class TestSaveAndLoad:
    def test_roundtrip(self, tmp_path: Path) -> None:
        from src.spending_guard import _current_month
        path = tmp_path / "spend.json"
        ledger = {"month": _current_month(), "entries": [{"cost_usd": 0.123}]}
        save_ledger(ledger, path)
        loaded = load_ledger(path)
        assert loaded["entries"][0]["cost_usd"] == 0.123


class TestMonthlyTotal:
    def test_sums_entries(self) -> None:
        ledger = {"entries": [{"cost_usd": 0.05}, {"cost_usd": 0.10}]}
        assert monthly_total(ledger) == pytest.approx(0.15)

    def test_empty_entries(self) -> None:
        assert monthly_total({"entries": []}) == 0.0


class TestComputeCost:
    def test_known_model_sonnet(self) -> None:
        cost = compute_cost("claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        expected = (1000 * 3.00 / 1_000_000) + (500 * 15.00 / 1_000_000)
        assert cost == pytest.approx(expected)

    def test_known_model_haiku(self) -> None:
        cost = compute_cost("claude-haiku-4-5", input_tokens=2000, output_tokens=100)
        expected = (2000 * 0.80 / 1_000_000) + (100 * 4.00 / 1_000_000)
        assert cost == pytest.approx(expected)

    def test_unknown_model_uses_default(self) -> None:
        cost = compute_cost("some-future-model", input_tokens=1000, output_tokens=500)
        expected = (1000 * 5.00 / 1_000_000) + (500 * 25.00 / 1_000_000)
        assert cost == pytest.approx(expected)


class TestCanSpend:
    def test_within_budget(self) -> None:
        ledger = {"entries": [{"cost_usd": 1.0}]}
        assert can_spend(ledger, budget=10.0, estimated_cost=0.15) is True

    def test_exceeds_budget(self) -> None:
        ledger = {"entries": [{"cost_usd": 9.90}]}
        assert can_spend(ledger, budget=10.0, estimated_cost=0.15) is False

    def test_already_exhausted(self) -> None:
        ledger = {"entries": [{"cost_usd": 10.0}]}
        assert can_spend(ledger, budget=10.0, estimated_cost=0.01) is False

    def test_warning_at_threshold(self, caplog: pytest.LogCaptureFixture) -> None:
        ledger = {"entries": [{"cost_usd": 8.50}]}
        with caplog.at_level(logging.WARNING):
            result = can_spend(ledger, budget=10.0, estimated_cost=0.10, warn_threshold=0.80)
        assert result is True
        assert "85%" in caplog.text


class TestRecordSpend:
    def test_appends_entry(self) -> None:
        from src.spending_guard import _current_month
        ledger = {"month": _current_month(), "entries": []}
        cost = record_spend(ledger, "anthropic", "claude-haiku-4-5",
                            input_tokens=1000, output_tokens=100, caller="test")
        assert len(ledger["entries"]) == 1
        entry = ledger["entries"][0]
        assert entry["provider"] == "anthropic"
        assert entry["model"] == "claude-haiku-4-5"
        assert entry["caller"] == "test"
        assert entry["cost_usd"] == pytest.approx(cost, abs=1e-6)

    def test_override_cost(self) -> None:
        ledger = {"entries": []}
        cost = record_spend(ledger, "pricelabs", "api-v1",
                            input_tokens=0, output_tokens=0,
                            caller="pricelabs", override_cost=0.02)
        assert cost == 0.02
        assert ledger["entries"][0]["cost_usd"] == 0.02
