"""Eval metrics — programmatic, no LLM judge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from traceiq.evals.baselines import Diagnosis


@dataclass
class Score:
    service_top1: bool
    category_ok: bool
    trigger_ok: bool
    correct_abstain: bool
    false_abstain: bool


def score_diagnosis(diag: Diagnosis, truth: dict[str, Any]) -> Score:
    solvable = bool(truth.get("solvable", True))
    if not solvable:
        return Score(
            service_top1=False,
            category_ok=False,
            trigger_ok=False,
            correct_abstain=diag.abstained,
            false_abstain=False,
        )
    return Score(
        service_top1=(diag.service == truth.get("root_cause_service")) and not diag.abstained,
        category_ok=(diag.category is None) or (diag.category == truth.get("category")),
        trigger_ok=_trigger_match(diag.trigger_change_id, truth.get("trigger_change_id")),
        correct_abstain=False,
        false_abstain=diag.abstained,
    )


def _trigger_match(got: str | None, expected: str | None) -> bool:
    if expected in (None, "null"):
        return got in (None, "", "null")
    return got == expected


def aggregate(scores: list[Score]) -> dict[str, float]:
    n = max(1, len(scores))
    return {
        "service_top1": sum(1 for s in scores if s.service_top1) / n,
        "category_ok": sum(1 for s in scores if s.category_ok) / n,
        "trigger_ok": sum(1 for s in scores if s.trigger_ok) / n,
        "correct_abstain": sum(1 for s in scores if s.correct_abstain) / n,
        "false_abstain": sum(1 for s in scores if s.false_abstain) / n,
        "n": float(len(scores)),
    }
