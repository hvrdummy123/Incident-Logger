"""Correlate anomaly onsets with nearby change events."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChangeEvent:
    id: str
    ts_ms: int
    kind: str
    service: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class ChangeHit:
    change_id: str
    service: str
    ts_ms: int
    delta_ms: int
    score: float
    reason: str


def correlate_changes(
    onset_ts: int,
    onset_service: str,
    changes: list[ChangeEvent],
    *,
    lookback_ms: int = 30 * 60_000,
    downstream: set[str] | None = None,
) -> list[ChangeHit]:
    downstream = downstream or set()
    hits: list[ChangeHit] = []
    for c in changes:
        if c.ts_ms > onset_ts or onset_ts - c.ts_ms > lookback_ms:
            continue
        delta = onset_ts - c.ts_ms
        score = 1.0 - (delta / lookback_ms)
        reason = "proximity"
        if c.service == onset_service:
            score += 1.0
            reason = "same_service"
        elif c.service in downstream:
            score += 0.5
            reason = "upstream_of_failing"
        hits.append(
            ChangeHit(
                change_id=c.id,
                service=c.service,
                ts_ms=c.ts_ms,
                delta_ms=delta,
                score=score,
                reason=reason,
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits
