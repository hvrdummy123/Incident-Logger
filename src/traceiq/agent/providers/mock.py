"""Deterministic mock provider for tests and offline runs."""

from __future__ import annotations

import json
from typing import Any


class MockProvider:
    name = "mock"

    def __init__(self, scripted: list[dict[str, Any]] | None = None) -> None:
        self.scripted = list(scripted or [])
        self.calls = 0

    def complete(self, messages: list[dict[str, str]], *, model: str) -> dict[str, Any]:
        self.calls += 1
        if self.scripted:
            item = self.scripted.pop(0)
            return {
                "content": item.get("content", ""),
                "tokens_in": item.get("tokens_in", 10),
                "tokens_out": item.get("tokens_out", 10),
                "cost_usd": item.get("cost_usd", 0.0),
                "tool_calls": item.get("tool_calls", []),
            }
        # Default: ask to submit a thin abstain report
        report = {
            "summary": "Insufficient evidence for a confident root cause.",
            "outcome": "abstained",
            "confidence": 0.2,
            "impact": {"services": [], "start": "", "end": "", "symptoms": []},
            "timeline": [],
            "root_cause": {
                "service": "",
                "category": "",
                "trigger_change_id": None,
                "explanation": "abstained",
                "evidence": [],
            },
            "contributing_factors": [],
            "ruled_out": [],
            "suggested_actions": [],
            "data_gaps": ["mock provider default path"],
            "open_questions": [],
            "run": {
                "model": model,
                "prompt_version": "mock",
                "steps": 0,
                "tokens": 0,
                "cost_usd": 0.0,
                "deterministic_only": False,
            },
        }
        return {
            "content": json.dumps(report),
            "tokens_in": 20,
            "tokens_out": 40,
            "cost_usd": 0.0,
            "tool_calls": [{"name": "submit_report", "arguments": report}],
        }
