"""Parse report shown in UI / `traceiq ingest --dry-run`."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from traceiq.ingest.types import LogEvent


@dataclass
class ParseReport:
    lines_read: int = 0
    lines_parsed: int = 0
    lines_unparsed: int = 0
    format: str = ""
    detect_confidence: float = 0.0
    unparsed_examples: list[str] = field(default_factory=list)
    ts_min_ms: int | None = None
    ts_max_ms: int | None = None
    timezone_assumption: str = "UTC"
    services: list[str] = field(default_factory=list)
    level_counts: dict[str, int] = field(default_factory=dict)
    duplicate_lines: int = 0
    out_of_order: int = 0
    inherited_timestamps: int = 0
    truncated_lines: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_report(
    events: list[LogEvent],
    *,
    fmt: str,
    confidence: float,
    max_unparsed_examples: int = 5,
) -> ParseReport:
    levels: Counter[str] = Counter()
    services: set[str] = set()
    unparsed: list[str] = []
    seen: set[str] = set()
    dupes = 0
    ooo = 0
    inherited = 0
    prev_ts: int | None = None
    ts_min: int | None = None
    ts_max: int | None = None
    parsed = 0

    for ev in events:
        levels[ev.level] += 1
        services.add(ev.service)
        if ev.timestamp_inherited:
            inherited += 1
        key = ev.raw
        if key in seen:
            dupes += 1
        else:
            seen.add(key)
        if not ev.parse_ok:
            if len(unparsed) < max_unparsed_examples:
                unparsed.append(ev.raw[:500])
        else:
            parsed += 1
        if ev.ts_ms is not None:
            if prev_ts is not None and ev.ts_ms < prev_ts:
                ooo += 1
            prev_ts = ev.ts_ms
            ts_min = ev.ts_ms if ts_min is None else min(ts_min, ev.ts_ms)
            ts_max = ev.ts_ms if ts_max is None else max(ts_max, ev.ts_ms)

    return ParseReport(
        lines_read=len(events),
        lines_parsed=parsed,
        lines_unparsed=len(events) - parsed,
        format=fmt,
        detect_confidence=confidence,
        unparsed_examples=unparsed,
        ts_min_ms=ts_min,
        ts_max_ms=ts_max,
        services=sorted(services),
        level_counts=dict(levels),
        duplicate_lines=dupes,
        out_of_order=ooo,
        inherited_timestamps=inherited,
    )
