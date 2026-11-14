"""Deterministic mock provider for tests and offline runs."""

from __future__ import annotations

import json
import re
from typing import Any


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
    ) -> None:
        self.scripted = list(scripted or [])
        self.briefing = briefing
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

        # Prefer an injected briefing — egress redaction can mangle JSON floats.
        briefing = self.briefing or _extract_briefing(messages)
        suspects = briefing.get("suspects") or []
        conf = float(briefing.get("confidence") or 0.0)
        top = suspects[0] if suspects else None
        top_svc = str(top.get("service") or "") if isinstance(top, dict) else ""
        top_score = float(top.get("score") or 0.0) if isinstance(top, dict) else 0.0
        hits = briefing.get("change_hits") or []
        trigger = hits[0].get("change_id") if hits else None
        change_desc = ""
        if hits:
            change_desc = str(hits[0].get("reason") or hits[0].get("change_id") or "")

        found = bool(top_svc) and (conf >= 0.15 or top_score >= 1.5)
        if found:
            report = {
                "summary": (
                    f"Mock investigator (from briefing) suspects {top_svc}"
                    + (f" near change {trigger}." if trigger else ".")
                ),
                "outcome": "root_cause_found",
                "confidence": max(conf, min(0.85, 0.35 + top_score / 10)),
                "impact": {
                    "services": [top_svc],
                    "start": "",
                    "end": "",
                    "symptoms": [
                        {
                            "text": f"Elevated errors / new templates on {top_svc}",
                            "evidence": [],
                        }
                    ],
                },
                "timeline": [
                    {
                        "ts": str(h.get("ts_ms") or ""),
                        "text": f"change hit on {h.get('service')}: {h.get('reason', '')}",
                        "evidence": [],
                    }
                    for h in hits[:5]
                ],
                "root_cause": {
                    "service": top_svc,
                    "category": "deploy" if trigger else "unknown",
                    "trigger_change_id": trigger,
                    "explanation": (
                        "Ranked top suspect from deterministic briefing"
                        + (f" ({change_desc})" if change_desc else "")
                        + "."
                    ),
                    "evidence": [],
                },
                "contributing_factors": [],
                "ruled_out": [
                    {
                        "hypothesis": s.get("service"),
                        "why": "lower suspect score than top",
                        "evidence": [],
                    }
                    for s in suspects[1:4]
                    if isinstance(s, dict)
                ],
                "suggested_actions": [
                    {
                        "text": f"Roll back or fix recent config/deploy on {top_svc}",
                        "type": "mitigation",
                        "risk": "medium",
                    }
                ],
                "data_gaps": list(briefing.get("data_gaps") or []),
                "open_questions": [],
                "run": {
                    "model": model,
                    "prompt_version": "mock-briefing",
                    "steps": 1,
                    "tokens": 0,
                    "cost_usd": 0.0,
                    "deterministic_only": False,
                },
            }
        else:
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
                "data_gaps": list(briefing.get("data_gaps") or [])
                or ["mock provider default path"],
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
