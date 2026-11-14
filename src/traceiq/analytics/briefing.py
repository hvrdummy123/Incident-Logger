"""Deterministic briefing assembled before any model call."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from traceiq.analytics.anomalies import Anomaly, cusum_anomalies, robust_z_anomalies
from traceiq.analytics.changes import ChangeEvent, ChangeHit, correlate_changes
from traceiq.analytics.graph import EdgeStat, build_service_graph
from traceiq.analytics.newtemplates import NewTemplate, find_new_templates
from traceiq.analytics.suspects import Suspect, confidence_from_margin, rank_suspects
from traceiq.analytics.timeline import TimelineEvent, build_timeline


@dataclass
class Briefing:
    timeline: list[TimelineEvent] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    new_templates: list[NewTemplate] = field(default_factory=list)
    change_hits: list[ChangeHit] = field(default_factory=list)
    suspects: list[Suspect] = field(default_factory=list)
    graph: list[EdgeStat] = field(default_factory=list)
    confidence: float = 0.0
    data_gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline": [asdict(x) for x in self.timeline],
            "anomalies": [asdict(x) for x in self.anomalies],
            "new_templates": [asdict(x) for x in self.new_templates],
            "change_hits": [asdict(x) for x in self.change_hits],
            "suspects": [
                {
                    "service": s.service,
                    "score": s.score,
                    "contributions": [asdict(c) for c in s.contributions],
                }
                for s in self.suspects
            ],
            "graph": [asdict(x) for x in self.graph],
            "confidence": self.confidence,
            "data_gaps": self.data_gaps,
        }


def build_briefing(
    *,
    metric_series: dict[str, list[tuple[int, float]]],
    templates: list[dict[str, Any]],
    changes: list[ChangeEvent],
    span_edges: list[tuple[str, str, bool]],
    reference_ms: int,
    data_gaps: list[str] | None = None,
) -> Briefing:
    anomalies: list[Anomaly] = []
    for name, pts in metric_series.items():
        anomalies.extend(robust_z_anomalies(name, pts))
        anomalies.extend(cusum_anomalies(name, pts))

    new_tpl = find_new_templates(templates, reference_ms=reference_ms)
    graph = build_service_graph(span_edges)

    # Correlate against earliest anomaly onset if any
    change_hits: list[ChangeHit] = []
    if anomalies:
        earliest = min(anomalies, key=lambda a: a.onset_ts)
        svc = earliest.series.split(".", 1)[0]
        change_hits = correlate_changes(earliest.onset_ts, svc, changes)

    suspects = rank_suspects(
        anomalies=anomalies, changes=change_hits, new_templates=new_tpl
    )
    timeline = build_timeline(
        changes=changes, anomalies=anomalies, new_templates=new_tpl
    )
    return Briefing(
        timeline=timeline,
        anomalies=anomalies,
        new_templates=new_tpl,
        change_hits=change_hits,
        suspects=suspects,
        graph=graph,
        confidence=confidence_from_margin(suspects),
        data_gaps=list(data_gaps or []),
    )
