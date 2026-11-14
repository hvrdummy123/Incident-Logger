"""Service dependency graph from span edges."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EdgeStat:
    src: str
    dst: str
    calls: int
    errors: int
    error_rate: float


def build_service_graph(
    edges: list[tuple[str, str, bool]],
) -> list[EdgeStat]:
    """edges: (caller_service, callee_service, is_error)."""
    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for src, dst, err in edges:
        counts[(src, dst)][0] += 1
        if err:
            counts[(src, dst)][1] += 1
    out: list[EdgeStat] = []
    for (src, dst), (calls, errors) in sorted(counts.items()):
        out.append(
            EdgeStat(
                src=src,
                dst=dst,
                calls=calls,
                errors=errors,
                error_rate=(errors / calls) if calls else 0.0,
            )
        )
    return out


def upstream_of(graph: list[EdgeStat], service: str) -> set[str]:
    """Services that call `service` (direct)."""
    return {e.src for e in graph if e.dst == service}
