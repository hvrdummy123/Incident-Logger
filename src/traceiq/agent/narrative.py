"""Build an honest, in-depth report from an imperfect briefing + log stats."""

from __future__ import annotations

from typing import Any

from traceiq.agent.schema import (
    Action,
    ErrorSeries,
    Factor,
    Impact,
    Report,
    ReportViz,
    RootCause,
    RuledOut,
    RunMeta,
    SeriesPoint,
    SuspectScore,
    Symptom,
    TimelineItem,
    TimelineMark,
)

PROMPT_VERSION = "narrative-v1"


def _top_suspects(briefing: dict[str, Any], n: int = 5) -> list[dict[str, Any]]:
    return [s for s in (briefing.get("suspects") or [])[:n] if isinstance(s, dict)]


def _ask_for_more(briefing: dict[str, Any], *, multi_fault: bool) -> list[str]:
    asks: list[str] = [
        "Change / deploy tickets around the onset window (service, version, author).",
        "Service-level golden metrics (error rate, latency, saturation) for the top suspects.",
        "Distributed traces for a few failing checkout/payment requests.",
    ]
    if multi_fault:
        asks.append(
            "Whether these failures started together or in sequence "
            "(page timestamps / incident channel timeline)."
        )
    hits = briefing.get("change_hits") or []
    if len(hits) > 1:
        asks.append(
            "Confirm which of the nearby changes were intentional and which were rollbacks."
        )
    if not briefing.get("graph"):
        asks.append(
            "Dependency / call-graph edges or service catalog links "
            "for blast-radius checks."
        )
    asks.append(
        "Any logs from the minutes immediately before onset that were rotated or sampled away."
    )
    return asks


def _build_viz(briefing: dict[str, Any], *, confidence: float) -> ReportViz:
    suspects = _top_suspects(briefing, 8)
    scores = [
        SuspectScore(service=str(s.get("service")), score=float(s.get("score") or 0.0))
        for s in suspects
        if s.get("service")
    ]

    series_out: list[ErrorSeries] = []
    raw_series = briefing.get("error_series") or {}
    if isinstance(raw_series, dict):
        # Prefer top suspect services; fall back to whatever is present.
        prefer = [s.service for s in scores] or list(raw_series.keys())
        for svc in prefer[:5]:
            pts = raw_series.get(svc) or raw_series.get(f"{svc}.error_rate") or []
            if not isinstance(pts, list) or not pts:
                continue
            points: list[SeriesPoint] = []
            for p in pts:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    points.append(SeriesPoint(ts_ms=int(p[0]), value=float(p[1])))
                elif isinstance(p, dict) and "ts_ms" in p:
                    points.append(
                        SeriesPoint(ts_ms=int(p["ts_ms"]), value=float(p.get("value") or 0))
                    )
            if points:
                series_out.append(ErrorSeries(service=str(svc).split(".", 1)[0], points=points))

    marks: list[TimelineMark] = []
    if briefing.get("reference_ms"):
        marks.append(
            TimelineMark(
                ts_ms=int(briefing["reference_ms"]),
                label="Estimated onset",
                kind="onset",
            )
        )
    for h in (briefing.get("change_hits") or [])[:8]:
        if not isinstance(h, dict):
            continue
        ts = h.get("ts_ms")
        if ts is None:
            continue
        marks.append(
            TimelineMark(
                ts_ms=int(ts),
                label=f"change:{h.get('service') or '?'}",
                kind="change",
            )
        )
    for a in (briefing.get("anomalies") or [])[:6]:
        if not isinstance(a, dict):
            continue
        ts = a.get("onset_ts") or a.get("ts_ms")
        if ts is None:
            continue
        series = str(a.get("series") or "error")
        marks.append(
            TimelineMark(
                ts_ms=int(ts),
                label=f"anomaly:{series.split('.', 1)[0]}",
                kind="error",
            )
        )
    marks.sort(key=lambda m: m.ts_ms)

    return ReportViz(
        suspect_scores=scores,
        error_series=series_out,
        timeline_marks=marks[:20],
        confidence=float(confidence),
    )


def apply_citations(report: Report, cites: dict[str, str]) -> Report:
    """Attach tool evidence ids produced during the investigation loop."""
    briefing_eid = cites.get("briefing")
    templates_eid = cites.get("templates")
    changes_eid = cites.get("changes")
    core = [e for e in (briefing_eid, templates_eid, changes_eid) if e]
    if not core:
        return report

    if report.outcome == "root_cause_found" and not report.root_cause.evidence:
        report.root_cause.evidence = list(core)

    for s in report.impact.symptoms:
        if not s.evidence:
            # Template-ish symptoms cite templates; score lines cite briefing.
            if "Template on" in s.text and templates_eid:
                s.evidence = [templates_eid]
            elif briefing_eid:
                s.evidence = [briefing_eid]

    for t in report.timeline:
        if not t.evidence:
            if "Change on" in t.text and changes_eid:
                t.evidence = [changes_eid]
            elif "onset" in t.text.lower() and briefing_eid:
                t.evidence = [briefing_eid]
            elif core:
                t.evidence = [core[0]]

    for f in report.contributing_factors:
        if not f.evidence and briefing_eid:
            f.evidence = [briefing_eid]

    for r in report.ruled_out:
        if not r.evidence:
            if "change" in r.hypothesis.lower() and changes_eid:
                r.evidence = [changes_eid]
            elif briefing_eid:
                r.evidence = [briefing_eid]

    # Drop soft gap if we now have citations
    if report.root_cause.evidence:
        report.data_gaps = [
            g
            for g in report.data_gaps
            if "lacks stored evidence citations" not in g
        ]
    return report


def build_narrative_report(
    briefing: dict[str, Any],
    *,
    model: str,
    deterministic_only: bool = False,
    cites: dict[str, str] | None = None,
) -> Report:
    suspects = _top_suspects(briefing, 6)
    conf = float(briefing.get("confidence") or 0.0)
    hits = [h for h in (briefing.get("change_hits") or []) if isinstance(h, dict)]
    templates = [t for t in (briefing.get("new_templates") or []) if isinstance(t, dict)]
    event_count = int(briefing.get("event_count") or 0)
    gaps = list(briefing.get("data_gaps") or [])

    top = suspects[0] if suspects else None
    top_svc = str(top.get("service") or "") if top else ""
    top_score = float(top.get("score") or 0.0) if top else 0.0
    second = suspects[1] if len(suspects) > 1 else None
    second_score = float(second.get("score") or 0.0) if second else 0.0

    multi_fault = bool(second and second_score >= max(1.5, top_score * 0.55))
    found = bool(top_svc) and (conf >= 0.12 or top_score >= 1.2)

    symptoms: list[Symptom] = []
    for s in suspects[:4]:
        svc = str(s.get("service") or "")
        score = float(s.get("score") or 0.0)
        if not svc:
            continue
        symptoms.append(
            Symptom(
                text=f"{svc} ranked as an active failure signal (suspect score {score:.2f}).",
                evidence=[],
            )
        )
    errorish = [
        t
        for t in templates
        if any(
            k in str(t.get("pattern") or "").lower()
            for k in ("error", "timeout", "panic", "500", "fail", "exhaust", "denied")
        )
    ]
    for t in errorish[:6]:
        symptoms.append(
            Symptom(
                text=(
                    f"Template on {t.get('service')}: "
                    f"{str(t.get('pattern') or '')[:140]} "
                    f"(after-onset count≈{t.get('count_after')})"
                ),
                evidence=[],
            )
        )

    timeline: list[TimelineItem] = []
    for h in hits[:8]:
        timeline.append(
            TimelineItem(
                ts=str(h.get("ts_ms") or ""),
                text=(
                    f"Change on {h.get('service')} "
                    f"({h.get('reason') or h.get('change_id')}; "
                    f"Δ={h.get('delta_ms')}ms before reference onset)"
                ),
                evidence=[],
            )
        )
    if briefing.get("reference_ms"):
        timeline.insert(
            0,
            TimelineItem(
                ts=str(briefing.get("reference_ms")),
                text="Estimated error-onset reference from log volume (imperfect; logs only).",
                evidence=[],
            ),
        )

    # Contributing = material secondary suspects (not weak decoys)
    contributing: list[Factor] = []
    contrib_svcs: set[str] = set()
    for s in suspects[1:6]:
        svc = str(s.get("service") or "")
        score = float(s.get("score") or 0.0)
        if not svc or svc == top_svc:
            continue
        if score < max(2.0, top_score * 0.35):
            continue
        bits = []
        for c in (s.get("contributions") or [])[:3]:
            if isinstance(c, dict):
                bits.append(f"{c.get('kind')}:{c.get('detail')}")
        contributing.append(
            Factor(
                text=(
                    f"{svc} remains in play (score {score:.2f})"
                    + (f" — {'; '.join(bits)}" if bits else "")
                    + (
                        ". May be cascade, concurrent fault, or shared dependency."
                        if multi_fault
                        else "."
                    )
                ),
                evidence=[],
            )
        )
        contrib_svcs.add(svc)
        if len(contributing) >= 3:
            break

    # Ruled out = weak suspects / decoy changes — never overlap contributing
    ruled: list[RuledOut] = []
    ruled_seen: set[str] = set()
    for s in suspects[1:8]:
        svc = str(s.get("service") or "")
        score = float(s.get("score") or 0.0)
        if not svc or svc == top_svc or svc in contrib_svcs or svc in ruled_seen:
            continue
        if score >= max(2.0, top_score * 0.35):
            continue
        ruled.append(
            RuledOut(
                hypothesis=svc,
                why=(
                    "Lower relative suspect score vs the lead; "
                    "keep watching if new evidence arrives."
                ),
                evidence=[],
            )
        )
        ruled_seen.add(svc)

    decoy_svcs: set[str] = set()
    for h in hits:
        svc = str(h.get("service") or "")
        if (
            svc
            and svc != top_svc
            and svc not in contrib_svcs
            and str(h.get("reason") or "") == "proximity"
            and svc not in decoy_svcs
        ):
            ruled.append(
                RuledOut(
                    hypothesis=f"nearby change on {svc}",
                    why=(
                        "Change is in-window but only proximity-correlated; "
                        "weaker than same-service hits."
                    ),
                    evidence=[],
                )
            )
            decoy_svcs.add(svc)

    asks = _ask_for_more(briefing, multi_fault=multi_fault)
    if event_count and event_count < 500:
        gaps.append("Log volume is small for an industry outage window — sampling bias likely.")
    if not hits:
        gaps.append("No deploy/config markers found in logs; root cause may predate this file.")
    if multi_fault:
        gaps.append(
            "Multiple strong suspects — a single root cause is uncertain; "
            "treat as a multi-factor incident."
        )
    # Only claim missing metrics if we truly have no series
    if not (briefing.get("error_series") or {}):
        gaps.append("No attached metrics time series (error/latency/saturation).")
    else:
        gaps.append(
            "Error-rate series derived from logs only (not golden signals / APM metrics)."
        )
    gaps.append(
        "No traces or change-management export; correlation uses log-embedded markers only."
    )

    if found and not multi_fault:
        summary = (
            f"From {event_count or 'the'} uploaded log lines, "
            f"the strongest signal is **{top_svc}** "
            f"(confidence {conf:.2f}). Nearby change activity and error patterns support a "
            f"deploy/config-class incident centered there. Evidence is incomplete; this is a "
            f"working theory, not a closed postmortem."
        )
        outcome = "root_cause_found"
        category = "deploy" if hits and str(hits[0].get("service")) == top_svc else "unknown"
        explanation = (
            f"Lead suspect {top_svc} (score {top_score:.2f}) from deterministic ranking over "
            f"error-rate shifts, new/high after-onset templates, and change proximity. "
            f"Logs are imperfect; secondary signals on "
            f"{', '.join(str(s.get('service')) for s in suspects[1:3]) or 'n/a'} "
            f"may be cascade or coincidence."
        )
        trigger = hits[0].get("change_id") if hits else None
        actions = [
            Action(
                text=(
                    f"Stabilize {top_svc}: roll back or fix the most recent "
                    "config/deploy, then re-check error rate."
                ),
                type="mitigation",
                risk="medium",
            ),
            Action(
                text=(
                    "Pull change tickets + metrics for the top 3 suspects "
                    "before declaring a single root cause."
                ),
                type="follow_up",
                risk="low",
            ),
        ]
    elif found and multi_fault:
        summary = (
            f"Logs show a **multi-fault** picture: lead suspect **{top_svc}** "
            f"(score {top_score:.2f}) but **{second.get('service') if second else '?'}** "
            f"is close (score {second_score:.2f}). With incomplete telemetry, TraceIQ will not "
            f"force a single tidy root cause — both (or a shared dependency) may be real."
        )
        outcome = "root_cause_found"
        category = "multi_factor"
        explanation = (
            f"Primary lean: {top_svc}. Concurrent strong signal: "
            f"{second.get('service') if second else 'n/a'}. "
            "Recommend parallel mitigation tracks until metrics/traces separate cause from cascade."
        )
        trigger = hits[0].get("change_id") if hits else None
        actions = [
            Action(
                text=(
                    f"Page owners for {top_svc} and "
                    f"{second.get('service') if second else 'secondary'} together."
                ),
                type="mitigation",
                risk="medium",
            ),
            Action(
                text=(
                    "Compare onset order across services (first ERROR burst) "
                    "before blaming a single deploy."
                ),
                type="follow_up",
                risk="low",
            ),
            Action(
                text="Export DB pool / cache / dependency SLOs for the blast-radius services.",
                type="follow_up",
                risk="low",
            ),
        ]
    else:
        summary = (
            f"Parsed {event_count or 0} log events but could not name a confident root cause. "
            "Below is what the logs do support, plus the data that would change the call."
        )
        outcome = "abstained"
        category = ""
        explanation = "Insufficient separation between suspects or too little structured signal."
        trigger = None
        top_svc = ""
        actions = [
            Action(
                text="Provide a wider time window and any deploy/changelog export for the window.",
                type="follow_up",
                risk="low",
            ),
        ]

    services = [str(s.get("service")) for s in suspects[:5] if s.get("service")]
    viz_conf = min(0.85, max(conf, 0.35 if found else conf))
    report = Report(
        summary=summary,
        outcome=outcome,  # type: ignore[arg-type]
        confidence=viz_conf,
        impact=Impact(services=services, symptoms=symptoms),
        timeline=timeline,
        root_cause=RootCause(
            service=top_svc,
            category=category,
            trigger_change_id=str(trigger) if trigger else None,
            explanation=explanation,
            evidence=[],
        ),
        contributing_factors=contributing,
        ruled_out=ruled,
        suggested_actions=actions,
        data_gaps=gaps,
        open_questions=asks,
        viz=_build_viz(briefing, confidence=viz_conf),
        run=RunMeta(
            model=model,
            prompt_version=PROMPT_VERSION,
            steps=0,
            tokens=0,
            cost_usd=0.0,
            deterministic_only=deterministic_only,
        ),
    )
    if cites:
        report = apply_citations(report, cites)
    return report
