"""Build a deterministic briefing from raw uploaded log text (BYO path)."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from traceiq.analytics.briefing import Briefing, build_briefing
from traceiq.analytics.changes import ChangeEvent

_DEPLOY_RE = re.compile(
    r"config reload|deploy complete|version=(?P<ver>\S+)|source=deploy",
    re.I,
)
_NUM = re.compile(r"\b\d+\b")
_HEX = re.compile(r"\b[0-9a-f]{6,}\b", re.I)


def _parse_ts_ms(raw: str) -> int | None:
    s = raw.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return int(datetime.fromisoformat(s).timestamp() * 1000)
    except ValueError:
        return None


def _normalize_template(msg: str) -> str:
    t = _NUM.sub("<NUM>", msg)
    t = _HEX.sub("<HEX>", t)
    return t[:240]


def parse_log_lines(text: str) -> list[dict[str, Any]]:
    """Parse JSONL or loosely structured lines into {ts_ms, service, level, msg}."""
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        service = "unknown"
        level = "INFO"
        msg = line
        ts_ms: int | None = None
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict):
                service = str(obj.get("service") or obj.get("svc") or "unknown")
                level = str(obj.get("level") or obj.get("severity") or "INFO").upper()
                msg = str(obj.get("msg") or obj.get("message") or obj.get("log") or line)
                ts_raw = obj.get("ts") or obj.get("timestamp") or obj.get("time") or ""
                ts_ms = _parse_ts_ms(str(ts_raw)) if ts_raw else None
        if ts_ms is None:
            continue
        events.append(
            {
                "ts_ms": ts_ms,
                "service": service,
                "level": level,
                "msg": msg,
            }
        )
    return events


def briefing_from_log_text(text: str) -> dict[str, Any]:
    events = parse_log_lines(text)
    if not events:
        return Briefing(
            data_gaps=["uploaded logs produced zero parseable timestamped events"]
        ).to_dict()

    # Error rate per service per minute
    buckets: dict[str, Counter[int]] = defaultdict(Counter)
    totals: dict[str, Counter[int]] = defaultdict(Counter)
    for ev in events:
        minute = ev["ts_ms"] // 60_000
        svc = ev["service"]
        totals[svc][minute] += 1
        if ev["level"] in {"ERROR", "FATAL", "CRITICAL"} or "error" in ev["msg"].lower():
            buckets[svc][minute] += 1

    metric_series: dict[str, list[tuple[int, float]]] = {}
    for svc, mins in totals.items():
        series: list[tuple[int, float]] = []
        for minute in sorted(mins):
            err = buckets[svc].get(minute, 0)
            tot = max(1, mins[minute])
            series.append((minute * 60_000, err / tot))
        metric_series[f"{svc}.error_rate"] = series

    # Templates
    first_seen: dict[tuple[str, str], int] = {}
    counts: Counter[tuple[str, str]] = Counter()
    for ev in events:
        key = (ev["service"], _normalize_template(ev["msg"]))
        counts[key] += 1
        first_seen[key] = min(first_seen.get(key, ev["ts_ms"]), ev["ts_ms"])

    # Onset heuristic: first minute where global ERROR rate jumps
    global_err: Counter[int] = Counter()
    global_tot: Counter[int] = Counter()
    for ev in events:
        m = ev["ts_ms"] // 60_000
        global_tot[m] += 1
        if ev["level"] in {"ERROR", "FATAL", "CRITICAL"} or "error" in ev["msg"].lower():
            global_err[m] += 1
    minutes = sorted(global_tot)
    onset_minute = minutes[0] if minutes else events[0]["ts_ms"] // 60_000
    baseline_rates: list[float] = []
    for m in minutes:
        rate = global_err[m] / max(1, global_tot[m])
        if len(baseline_rates) >= 5:
            base = sum(baseline_rates[-10:]) / min(10, len(baseline_rates))
            if global_err[m] >= 5 and rate >= max(0.12, base * 3):
                onset_minute = m
                break
        baseline_rates.append(rate)
    reference_ms = onset_minute * 60_000

    templates: list[dict[str, Any]] = []
    for (svc, pattern), fs in first_seen.items():
        before = sum(
            1
            for ev in events
            if ev["service"] == svc
            and _normalize_template(ev["msg"]) == pattern
            and ev["ts_ms"] < reference_ms
        )
        after = counts[(svc, pattern)] - before
        templates.append(
            {
                "template_id": f"tpl_{hash(pattern) & 0xFFFFFFFF:x}",
                "service": svc,
                "pattern": pattern,
                "first_seen": fs,
                "count_before": before,
                "count_after": after,
                "count": counts[(svc, pattern)],
            }
        )

    changes: list[ChangeEvent] = []
    for i, ev in enumerate(events):
        if not _DEPLOY_RE.search(ev["msg"]):
            continue
        kind = "deploy" if "deploy" in ev["msg"].lower() else "config_change"
        changes.append(
            ChangeEvent(
                id=f"chg_{i}",
                ts_ms=ev["ts_ms"],
                kind=kind,
                service=ev["service"],
                description=ev["msg"][:200],
            )
        )

    # Cheap call graph from gateway upstream mentions
    span_edges: list[tuple[str, str, bool]] = []
    for ev in events:
        if ev["service"] == "gateway" and "upstream" in ev["msg"]:
            m = re.search(r"upstream\s+(\S+)", ev["msg"])
            if m:
                up = m.group(1).strip()
                failing = ev["level"] in {"ERROR", "WARN"} or "500" in ev["msg"]
                span_edges.append(("gateway", up, failing))

    briefing = build_briefing(
        metric_series=metric_series,
        templates=templates,
        changes=changes,
        span_edges=span_edges,
        reference_ms=reference_ms,
        data_gaps=[],
    )
    d = briefing.to_dict()
    d["event_count"] = len(events)
    d["reference_ms"] = reference_ms
    if not d.get("suspects"):
        d["data_gaps"] = list(d.get("data_gaps") or []) + [
            "no ranked suspects from uploaded logs"
        ]
    return d
