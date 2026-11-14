"""compare_windows — the agent's most useful deterministic tool."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WindowDiff:
    key: str
    before: float
    during: float
    delta: float
    ratio: float


def _rate(counts: dict[str, int], key: str, minutes: float) -> float:
    if minutes <= 0:
        return 0.0
    return counts.get(key, 0) / minutes


def compare_windows(
    before: list[dict[str, Any]],
    during: list[dict[str, Any]],
    *,
    before_minutes: float,
    during_minutes: float,
    key_field: str = "template_id",
    top_k: int = 20,
) -> list[WindowDiff]:
    """before/during: rows with key_field and count (or one row per event)."""
    b: dict[str, int] = defaultdict(int)
    d: dict[str, int] = defaultdict(int)
    for row in before:
        b[str(row[key_field])] += int(row.get("count", 1))
    for row in during:
        d[str(row[key_field])] += int(row.get("count", 1))
    keys = set(b) | set(d)
    diffs = [
        WindowDiff(
            key=k,
            before=_rate(b, k, before_minutes),
            during=_rate(d, k, during_minutes),
            delta=_rate(d, k, during_minutes) - _rate(b, k, before_minutes),
            ratio=(_rate(d, k, during_minutes) / _rate(b, k, before_minutes))
            if _rate(b, k, before_minutes) > 0
            else float("inf") if _rate(d, k, during_minutes) > 0 else 0.0,
        )
        for k in keys
    ]
    diffs.sort(key=lambda x: abs(x.delta), reverse=True)
    return diffs[:top_k]
