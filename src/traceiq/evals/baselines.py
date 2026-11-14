"""Non-LLM baseline agents for the eval harness."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class Diagnosis:
    service: str | None
    category: str | None
    trigger_change_id: str | None
    confidence: float
    abstained: bool = False
    agent: str = ""


def random_agent(services: list[str], *, seed: int) -> Diagnosis:
    rng = random.Random(seed)
    return Diagnosis(
        service=rng.choice(services) if services else None,
        category=None,
        trigger_change_id=None,
        confidence=0.1,
        agent="random",
    )


def most_errors_agent(error_counts: dict[str, int]) -> Diagnosis:
    if not error_counts:
        return Diagnosis(None, None, None, 0.0, abstained=True, agent="most_errors")
    svc = max(error_counts, key=lambda s: error_counts[s])
    return Diagnosis(svc, None, None, 0.4, agent="most_errors")


def latest_deploy_agent(
    changes: list[dict[str, Any]],
    *,
    onset_ts: int,
) -> Diagnosis:
    candidates = [
        c
        for c in changes
        if c.get("kind") in {"deploy", "config_change", "feature_flag"}
        and int(c.get("ts_ms") or c.get("ts") or 0) <= onset_ts
    ]
    if not candidates:
        return Diagnosis(None, None, None, 0.0, abstained=True, agent="latest_deploy")
    latest = max(candidates, key=lambda c: int(c.get("ts_ms") or c.get("ts") or 0))
    return Diagnosis(
        str(latest.get("service")),
        None,
        str(latest.get("id")),
        0.35,
        agent="latest_deploy",
    )


def deterministic_agent(briefing: dict[str, Any]) -> Diagnosis:
    suspects = briefing.get("suspects") or []
    if not suspects:
        return Diagnosis(None, None, None, 0.0, abstained=True, agent="deterministic")
    top = suspects[0]
    conf = float(briefing.get("confidence") or 0.0)
    # Abstain only when the top score is tiny or margin is noise-level.
    top_score = float(top.get("score") or 0.0)
    if conf < 0.08 and top_score < 1.0:
        return Diagnosis(
            top.get("service"),
            None,
            None,
            conf,
            abstained=True,
            agent="deterministic",
        )
    trigger = None
    hits = briefing.get("change_hits") or []
    if hits:
        trigger = hits[0].get("change_id")
    return Diagnosis(
        top.get("service"),
        None,
        trigger,
        conf,
        agent="deterministic",
    )


def oracle_agent(ground_truth: dict[str, Any]) -> Diagnosis:
    if not ground_truth.get("solvable", True):
        return Diagnosis(None, None, None, 1.0, abstained=True, agent="oracle")
    return Diagnosis(
        ground_truth.get("root_cause_service"),
        ground_truth.get("category"),
        ground_truth.get("trigger_change_id"),
        1.0,
        agent="oracle",
    )
