"""Deterministic mock provider for tests and offline runs."""

from __future__ import annotations

import json
import re
from typing import Any

from traceiq.agent.narrative import build_narrative_report


def _extract_briefing(messages: list[dict[str, str]]) -> dict[str, Any]:
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content") or ""
        m = re.search(r"<UNTRUSTED>\s*(\{.*\})\s*</UNTRUSTED>", content, re.S)
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


class MockProvider:
    name = "mock"

    def __init__(
        self,
        scripted: list[dict[str, Any]] | None = None,
        *,
        briefing: dict[str, Any] | None = None,
        cites: dict[str, str] | None = None,
    ) -> None:
        self.scripted = list(scripted or [])
        self.briefing = briefing
        self.cites = cites or {}
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

        briefing = self.briefing or _extract_briefing(messages)
        report_model = build_narrative_report(
            briefing,
            model=model,
            deterministic_only=False,
            cites=self.cites or None,
        )
        report = report_model.model_dump()
        return {
            "content": json.dumps(report),
            "tokens_in": 20,
            "tokens_out": 80,
            "cost_usd": 0.0,
            "tool_calls": [{"name": "submit_report", "arguments": report}],
        }
