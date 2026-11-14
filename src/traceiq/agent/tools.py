"""Read-only investigation tools with JSON-schema-ish validation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from traceiq.ids import evidence_id

TOOL_NAMES = {
    "get_briefing",
    "query_logs",
    "top_templates",
    "recent_changes",
    "compare_windows",
    "service_graph",
    "get_evidence",
    "update_hypotheses",
    "submit_report",
}


@dataclass
class ToolResult:
    ok: bool
    name: str
    data: Any
    evidence_ids: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ToolContext:
    briefing: dict[str, Any]
    evidence: dict[str, Any] = field(default_factory=dict)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    submitted_report: dict[str, Any] | None = None
    # optional callables for store-backed tools
    query_logs_fn: Callable[..., list[dict[str, Any]]] | None = None


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> ToolResult:
    if name not in TOOL_NAMES:
        return ToolResult(ok=False, name=name, data=None, error=f"unknown tool: {name}")

    if name == "get_briefing":
        eid = evidence_id()
        ctx.evidence[eid] = {"kind": "briefing", "data": ctx.briefing}
        return ToolResult(ok=True, name=name, data=ctx.briefing, evidence_ids=[eid])

    if name == "query_logs":
        limit = min(int(args.get("limit", 50)), 200)
        rows: list[dict[str, Any]]
        if ctx.query_logs_fn:
            rows = ctx.query_logs_fn(**{k: v for k, v in args.items() if k != "limit"})[:limit]
        else:
            # briefing-only fallback: empty
            rows = []
        eid = evidence_id()
        ctx.evidence[eid] = {"kind": "logs", "rows": rows, "args": args}
        return ToolResult(
            ok=True,
            name=name,
            data={"rows": rows, "truncated": False},
            evidence_ids=[eid],
        )

    if name == "top_templates":
        templates = (ctx.briefing.get("new_templates") or [])[: int(args.get("k", 10))]
        eid = evidence_id()
        ctx.evidence[eid] = {"kind": "templates", "data": templates}
        return ToolResult(ok=True, name=name, data=templates, evidence_ids=[eid])

    if name == "recent_changes":
        changes = ctx.briefing.get("change_hits") or []
        eid = evidence_id()
        ctx.evidence[eid] = {"kind": "changes", "data": changes}
        return ToolResult(ok=True, name=name, data=changes, evidence_ids=[eid])

    if name == "compare_windows":
        eid = evidence_id()
        data = {"note": "compare_windows requires store; use briefing suspects in mock mode"}
        ctx.evidence[eid] = {"kind": "compare", "data": data}
        return ToolResult(ok=True, name=name, data=data, evidence_ids=[eid])

    if name == "service_graph":
        graph = ctx.briefing.get("graph") or []
        eid = evidence_id()
        ctx.evidence[eid] = {"kind": "graph", "data": graph}
        return ToolResult(ok=True, name=name, data=graph, evidence_ids=[eid])

    if name == "get_evidence":
        eid = str(args.get("id", ""))
        if eid not in ctx.evidence:
            return ToolResult(ok=False, name=name, data=None, error="unknown evidence id")
        return ToolResult(ok=True, name=name, data=ctx.evidence[eid], evidence_ids=[eid])

    if name == "update_hypotheses":
        items = args.get("list") or args.get("hypotheses") or []
        if not isinstance(items, list):
            return ToolResult(ok=False, name=name, data=None, error="hypotheses must be a list")
        ctx.hypotheses = items
        return ToolResult(ok=True, name=name, data={"count": len(items)})

    if name == "submit_report":
        report = args if "summary" in args else args.get("report") or args
        ctx.submitted_report = report
        return ToolResult(ok=True, name=name, data={"accepted": True})

    return ToolResult(ok=False, name=name, data=None, error="unhandled")
