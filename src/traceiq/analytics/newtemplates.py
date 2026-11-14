"""Templates first seen after a reference time, or with a sharp rate jump."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NewTemplate:
    template_id: str
    service: str
    pattern: str
    first_seen_ms: int
    count_after: int
    score: float


def find_new_templates(
    templates: list[dict[str, Any]],
    *,
    reference_ms: int,
    rate_jump_factor: float = 5.0,
) -> list[NewTemplate]:
    """
    templates items: template_id, service, pattern, first_seen, count_before, count_after
    (counts optional — if missing, first_seen alone drives the score).
    """
    out: list[NewTemplate] = []
    for t in templates:
        first = int(t.get("first_seen") or t.get("first_seen_ms") or 0)
        before = int(t.get("count_before") or 0)
        after = int(t.get("count_after") or t.get("count") or 0)
        is_new = first >= reference_ms
        jumped = before > 0 and after / before >= rate_jump_factor
        if not (is_new or jumped):
            continue
        score = float(after) + (10.0 if is_new else 0.0) + (5.0 if jumped else 0.0)
        out.append(
            NewTemplate(
                template_id=str(t["template_id"]),
                service=str(t.get("service") or "unknown"),
                pattern=str(t.get("pattern") or ""),
                first_seen_ms=first,
                count_after=after,
                score=score,
            )
        )
    out.sort(key=lambda x: x.score, reverse=True)
    return out
