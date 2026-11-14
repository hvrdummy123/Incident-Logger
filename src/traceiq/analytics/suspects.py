"""Transparent weighted suspect ranking — weights tuned on train only (later)."""

from __future__ import annotations

from dataclasses import dataclass, field

from traceiq.analytics.anomalies import Anomaly
from traceiq.analytics.changes import ChangeHit
from traceiq.analytics.newtemplates import NewTemplate

# Defaults — tune on train split in M5; never on test.
WEIGHTS = {
    "anomaly": 1.0,
    "earliest_onset": 0.8,
    "change": 0.9,
    "new_template": 0.7,
}


@dataclass(frozen=True, slots=True)
class Contribution:
    kind: str
    detail: str
    points: float


@dataclass
class Suspect:
    service: str
    score: float
    contributions: list[Contribution] = field(default_factory=list)


def rank_suspects(
    *,
    anomalies: list[Anomaly],
    changes: list[ChangeHit],
    new_templates: list[NewTemplate],
    weights: dict[str, float] | None = None,
) -> list[Suspect]:
    w = {**WEIGHTS, **(weights or {})}
    scores: dict[str, Suspect] = {}

    def bump(service: str, kind: str, detail: str, points: float) -> None:
        s = scores.setdefault(service, Suspect(service=service, score=0.0))
        s.score += points
        s.contributions.append(Contribution(kind=kind, detail=detail, points=points))

    # anomaly strength + earliest onset bonus among anomalous services
    onsets = [(a.onset_ts, a.series.split(".", 1)[0], a.score) for a in anomalies]
    if onsets:
        earliest = min(ts for ts, _, _ in onsets)
        for ts, svc, sc in onsets:
            bump(svc, "anomaly", f"score={sc:.2f}", w["anomaly"] * min(sc / 4.0, 3.0))
            if ts == earliest:
                bump(svc, "earliest_onset", f"ts={ts}", w["earliest_onset"])

    for ch in changes[:10]:
        bump(ch.service, "change", ch.reason, w["change"] * ch.score)

    for nt in new_templates[:10]:
        pts = w["new_template"] * min(nt.score / 10.0, 2.0)
        bump(nt.service, "new_template", nt.template_id, pts)

    return sorted(scores.values(), key=lambda s: s.score, reverse=True)


def confidence_from_margin(suspects: list[Suspect]) -> float:
    if not suspects:
        return 0.0
    if len(suspects) == 1:
        return min(0.9, 0.4 + suspects[0].score / 10.0)
    gap = suspects[0].score - suspects[1].score
    return max(0.05, min(0.95, gap / max(suspects[0].score, 1e-9)))
