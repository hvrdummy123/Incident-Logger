"""Build an honest, in-depth report from an imperfect briefing + log stats."""

from __future__ import annotations

from typing import Any

from traceiq.agent.schema import (
    Action,
    Factor,
    Impact,
    Report,
    RootCause,
    RuledOut,
    RunMeta,
    Symptom,
    TimelineItem,
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
    # Always acknowledge incompleteness
    asks.append(
        "Any logs from the minutes immediately before onset that were rotated or sampled away."
    )
    return asks


def build_narrative_report(
    briefing: dict[str, Any],
    *,
    model: str,
    deterministic_only: bool = False,
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

    # Impact / symptoms from templates + suspect list
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

    contributing: list[Factor] = []
    for s in suspects[1:5] if found else suspects[:4]:
        svc = str(s.get("service") or "")
        if not svc:
            continue
        bits = []
        for c in (s.get("contributions") or [])[:3]:
            if isinstance(c, dict):
                bits.append(f"{c.get('kind')}:{c.get('detail')}")
        contributing.append(
            Factor(
                text=(
                    f"{svc} remains in play (score {float(s.get('score') or 0):.2f})"
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

    ruled: list[RuledOut] = []
    for s in suspects[3:6]:
        svc = str(s.get("service") or "")
        if not svc or svc == top_svc:
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
    # Explicitly call out classic decoys when present but weak
    for h in hits:
        svc = str(h.get("service") or "")
        if svc and svc != top_svc and str(h.get("reason") or "") == "proximity":
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
    gaps.extend(
        g
        for g in [
            "No attached metrics time series (error/latency/saturation).",
            "No traces or change-management export; correlation uses log-embedded markers only.",
        ]
        if g not in gaps
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
    return Report(
        summary=summary,
        outcome=outcome,  # type: ignore[arg-type]
        confidence=min(0.85, max(conf, 0.35 if found else conf)),
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
        run=RunMeta(
            model=model,
            prompt_version=PROMPT_VERSION,
            steps=0,
            tokens=0,
            cost_usd=0.0,
            deterministic_only=deterministic_only,
        ),
    )
