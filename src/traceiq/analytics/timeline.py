"""Merged notable-event timeline for the briefing."""

from __future__ import annotations

from dataclasses import dataclass

from traceiq.analytics.anomalies import Anomaly
from traceiq.analytics.changes import ChangeEvent
from traceiq.analytics.newtemplates import NewTemplate


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    ts_ms: int
    kind: str
    service: str
    text: str
    evidence_hint: str = ""


def build_timeline(
    *,
    changes: list[ChangeEvent],
    anomalies: list[Anomaly],
    new_templates: list[NewTemplate],
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for c in changes:
        events.append(
            TimelineEvent(
                ts_ms=c.ts_ms,
                kind="change",
                service=c.service,
                text=f"{c.kind}: {c.description or c.id}",
                evidence_hint=c.id,
            )
        )
    seen_svc: set[str] = set()
    for a in sorted(anomalies, key=lambda x: x.onset_ts):
        svc = a.series.split(".", 1)[0]
        if svc in seen_svc:
            continue
        seen_svc.add(svc)
        events.append(
            TimelineEvent(
                ts_ms=a.onset_ts,
                kind="anomaly",
                service=svc,
                text=f"{a.method} onset mag={a.magnitude:.3g}",
                evidence_hint=a.series,
            )
        )
    for nt in new_templates:
        events.append(
            TimelineEvent(
                ts_ms=nt.first_seen_ms,
                kind="new_template",
                service=nt.service,
                text=nt.pattern[:120],
                evidence_hint=nt.template_id,
            )
        )
    events.sort(key=lambda e: (e.ts_ms, e.kind))
    return events
