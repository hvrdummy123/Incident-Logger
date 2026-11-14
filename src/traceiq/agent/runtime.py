"""Durable-ish investigation loop (in-memory steps; Postgres wiring in M8)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from traceiq.agent.budgets import Budget
from traceiq.agent.schema import Report, parse_report
from traceiq.agent.state import Status, can_transition
from traceiq.agent.tools import ToolContext, run_tool
from traceiq.agent.verify import verify_report
from traceiq.safety.egress import EgressGateway
from traceiq.safety.injection import scan_for_injection
from traceiq.safety.redact import RedactionMap

PROMPT_VERSION = "investigator-v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "investigator.md"


@dataclass
class Step:
    seq: int
    kind: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


@dataclass
class InvestigationResult:
    status: Status
    report: Report | None
    steps: list[Step]
    verification: dict[str, Any]
    injection_suspected: bool
    spent_usd: float


def _system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _deterministic_report(briefing: dict[str, Any], *, model: str) -> Report:
    from traceiq.agent.narrative import build_narrative_report

    return build_narrative_report(briefing, model=model, deterministic_only=True)


def run_investigation(
    *,
    briefing: dict[str, Any],
    gateway: EgressGateway,
    provider: Any,
    model: str,
    budget: Budget | None = None,
    known_services: set[str] | None = None,
    cancel: dict[str, bool] | None = None,
    untrusted_log_snippets: list[str] | None = None,
) -> InvestigationResult:
    budget = budget or Budget()
    cancel = cancel or {"cancel": False}
    status = Status.QUEUED
    steps: list[Step] = []
    seq = 0
    mapping = RedactionMap(investigation_id="local")
    ctx = ToolContext(briefing=briefing)

    def transition(dst: Status) -> None:
        nonlocal status
        if not can_transition(status, dst):
            raise RuntimeError(f"illegal transition {status} -> {dst}")
        status = dst
        nonlocal seq
        seq += 1
        steps.append(Step(seq=seq, kind="state", name=dst.value))

    injection_hits = []
    for snippet in untrusted_log_snippets or []:
        injection_hits.extend(scan_for_injection(snippet))

    try:
        transition(Status.SCOPING)
        if cancel.get("cancel"):
            transition(Status.CANCELLED)
            return InvestigationResult(
                status,
                None,
                steps,
                {},
                bool(injection_hits),
                gateway.spent_usd,
            )

        transition(Status.BRIEFING)
        # Briefing already computed by caller — record tool use
        tr = run_tool(ctx, "get_briefing", {})
        seq += 1
        steps.append(Step(seq=seq, kind="tool", name="get_briefing", result=tr.data))

        # Degraded path: no model / mock-only forced by gateway policy
        use_model = not (gateway.no_external_llm and provider.name != "mock")
        if provider.name == "mock" or use_model:
            transition(Status.INVESTIGATING)
        else:
            transition(Status.REPORTING)
            report = _deterministic_report(briefing, model=model)
            transition(Status.ABSTAINED if report.outcome == "abstained" else Status.DONE)
            return InvestigationResult(
                status,
                report,
                steps,
                {"passed": True, "issues": []},
                bool(injection_hits),
                gateway.spent_usd,
            )

        # Simple loop: one model call that may submit_report or tool_calls
        while budget.exhausted() is None and ctx.submitted_report is None:
            if cancel.get("cancel"):
                transition(Status.CANCELLED)
                return InvestigationResult(
                    status, None, steps, {}, bool(injection_hits), gateway.spent_usd
                )
            # Compact + rounded floats (long decimals can trip card redaction).
            def _round_obj(obj: Any) -> Any:
                if isinstance(obj, float):
                    return round(obj, 4)
                if isinstance(obj, list):
                    return [_round_obj(x) for x in obj]
                if isinstance(obj, dict):
                    return {k: _round_obj(v) for k, v in obj.items()}
                return obj

            compact_briefing = _round_obj(
                {
                    "suspects": [
                        {
                            "service": s.get("service"),
                            "score": s.get("score"),
                            "contributions": [
                                {
                                    "kind": c.get("kind"),
                                    "detail": str(c.get("detail") or "")[:80],
                                    "points": c.get("points"),
                                }
                                for c in (s.get("contributions") or [])[:4]
                            ],
                        }
                        for s in (briefing.get("suspects") or [])[:8]
                    ],
                    "confidence": briefing.get("confidence"),
                    "change_hits": (briefing.get("change_hits") or [])[:8],
                    "new_templates": [
                        {
                            "service": t.get("service"),
                            "pattern": str(t.get("pattern") or "")[:120],
                            "count_after": t.get("count_after"),
                        }
                        for t in (briefing.get("new_templates") or [])[:8]
                    ],
                    "data_gaps": (briefing.get("data_gaps") or [])[:8],
                    "event_count": briefing.get("event_count"),
                }
            )
            messages = [
                {"role": "system", "content": _system_prompt()},
                {
                    "role": "user",
                    "content": (
                        "Investigate this incident. Briefing follows in an untrusted block.\n"
                        "<UNTRUSTED>\n"
                        + json.dumps(compact_briefing, default=str)
                        + "\n</UNTRUSTED>"
                    ),
                },
            ]
            try:
                resp = gateway.call(provider, model=model, messages=messages, mapping=mapping)
            except PermissionError:
                report = _deterministic_report(briefing, model=model)
                report.run.deterministic_only = True
                if can_transition(status, Status.REPORTING):
                    transition(Status.REPORTING)
                final = Status.ABSTAINED if report.outcome == "abstained" else Status.DONE
                if can_transition(status, final):
                    transition(final)
                else:
                    status = final
                    seq += 1
                    steps.append(Step(seq=seq, kind="state", name=final.value))
                return InvestigationResult(
                    status,
                    report,
                    steps,
                    {"passed": True, "degraded": True},
                    bool(injection_hits),
                    gateway.spent_usd,
                )

            budget.record(
                tokens=int(resp.get("tokens_in", 0)) + int(resp.get("tokens_out", 0)),
                cost=float(resp.get("cost_usd", 0.0)),
            )
            seq += 1
            steps.append(
                Step(
                    seq=seq,
                    kind="llm",
                    name="complete",
                    result={"content": resp.get("content", "")[:500]},
                    tokens_in=int(resp.get("tokens_in", 0)),
                    tokens_out=int(resp.get("tokens_out", 0)),
                    cost_usd=float(resp.get("cost_usd", 0.0)),
                )
            )

            for call in resp.get("tool_calls") or []:
                name = call.get("name", "")
                args = call.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tr = run_tool(ctx, name, args if isinstance(args, dict) else {})
                seq += 1
                steps.append(
                    Step(
                        seq=seq,
                        kind="tool",
                        name=name,
                        args=args if isinstance(args, dict) else {},
                        result={"ok": tr.ok, "error": tr.error, "evidence_ids": tr.evidence_ids},
                    )
                )
                budget.record()
                if name == "submit_report" and tr.ok:
                    break

            # If model returned JSON report content without tool call
            if ctx.submitted_report is None and resp.get("content"):
                try:
                    maybe = json.loads(resp["content"])
                    if isinstance(maybe, dict) and "summary" in maybe:
                        ctx.submitted_report = maybe
                except json.JSONDecodeError:
                    pass

            # Loop detector: identical tool name spam
            recent = [s.name for s in steps[-6:] if s.kind == "tool"]
            if len(recent) >= 6 and len(set(recent)) == 1:
                break

            # Mock default submits in one shot; stop after one LLM turn if report present
            if ctx.submitted_report is not None:
                break
            # Avoid infinite loop with empty scripted mock
            if provider.name == "mock" and not getattr(provider, "scripted", None):
                break

        transition(Status.VERIFYING)
        if ctx.submitted_report is None:
            report = _deterministic_report(briefing, model=model)
        else:
            try:
                report = parse_report(ctx.submitted_report)
            except Exception:  # noqa: BLE001
                report = _deterministic_report(briefing, model=model)

        if injection_hits:
            report.data_gaps = list(report.data_gaps) + ["injection_suspected in telemetry"]
            report.open_questions = list(report.open_questions) + [
                f"injection-like line: {injection_hits[0].line[:120]}"
            ]

        report.run.model = model
        report.run.prompt_version = PROMPT_VERSION
        report.run.steps = budget.steps
        report.run.tokens = budget.tokens
        report.run.cost_usd = budget.cost_usd

        v = verify_report(
            report,
            evidence_ids=set(ctx.evidence.keys()),
            known_services=known_services
            or {s.get("service", "") for s in (briefing.get("suspects") or [])},
        )
        # Force abstain only on hard verify failures. Missing citations (common on
        # BYO/mock before evidence rows are materialized) stays as a found-but-
        # unverified claim with a confidence cap.
        if report.outcome == "root_cause_found" and not v.passed:
            soft = {"missing_evidence", "root_cause_no_evidence"}
            hard = [i for i in v.issues if i.code not in soft]
            if hard:
                report.outcome = "abstained"
            else:
                report.confidence = min(float(report.confidence), 0.6)
                report.data_gaps = list(report.data_gaps) + [
                    "root-cause claim lacks stored evidence citations"
                ]

        transition(Status.REPORTING)
        final = Status.ABSTAINED if report.outcome == "abstained" else Status.DONE
        transition(final)
        return InvestigationResult(
            status=final,
            report=report,
            steps=steps,
            verification={
                "passed": v.passed,
                "issues": [{"code": i.code, "detail": i.detail} for i in v.issues],
                "unverified": v.unverified,
            },
            injection_suspected=bool(injection_hits),
            spent_usd=gateway.spent_usd,
        )
    except Exception as e:  # noqa: BLE001
        status = Status.FAILED
        seq += 1
        steps.append(Step(seq=seq, kind="state", name="FAILED", result={"error": str(e)}))
        return InvestigationResult(
            status,
            None,
            steps,
            {"error": str(e)},
            bool(injection_hits),
            gateway.spent_usd,
        )
