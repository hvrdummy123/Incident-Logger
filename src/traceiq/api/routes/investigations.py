"""Start / read investigations; SSE step stream."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from traceiq.agent.budgets import Budget
from traceiq.agent.providers.mock import MockProvider
from traceiq.agent.runtime import run_investigation
from traceiq.analytics.from_logs import briefing_from_log_text
from traceiq.api.deps import AuthUser, db_session, require_role, settings_dep
from traceiq.api.errors import AppError
from traceiq.api.sse import iter_steps_as_sse
from traceiq.audit.chain import append_audit
from traceiq.auth.rbac import Role
from traceiq.config import Settings
from traceiq.db.models import Investigation, InvestigationStep, Report
from traceiq.ids import new_ulid
from traceiq.safety.egress import EgressGateway
from traceiq.store.datasets import dataset_dir
from traceiq.tenancy.context import TenantContext, set_tenant
from traceiq.tenancy.scope import get_incident

router = APIRouter(tags=["investigations"])

# In-memory step cache for SSE until workers own the stream (M10).
_STEP_CACHE: dict[str, list[dict[str, Any]]] = {}


def _report_markdown(report: Any) -> str:
    lines = [
        f"# {report.summary}",
        "",
        f"Outcome: **{report.outcome}** (confidence {report.confidence:.2f})",
        "",
        "## Root cause",
        f"- Service: `{report.root_cause.service or '—'}`",
        f"- Category: {report.root_cause.category or '—'}",
        f"- {report.root_cause.explanation or ''}",
        "",
        "## Ruled out",
    ]
    for r in report.ruled_out:
        lines.append(f"- {r.hypothesis}: {r.why}")
    if not report.ruled_out:
        lines.append("- —")
    lines.extend(["", "## Data gaps"])
    for g in report.data_gaps:
        lines.append(f"- {g}")
    if not report.data_gaps:
        lines.append("- —")
    lines.extend(["", "## What would sharpen this"])
    for q in report.open_questions:
        lines.append(f"- {q}")
    if not report.open_questions:
        lines.append("- —")
    lines.extend(["", "## Contributing factors"])
    for f in report.contributing_factors:
        lines.append(f"- {f.text}")
    if not report.contributing_factors:
        lines.append("- —")
    return "\n".join(lines) + "\n"


@router.post("/incidents/{incident_id}/investigations", status_code=201)
def start_investigation(
    incident_id: str,
    user: AuthUser = Depends(require_role(Role.INVESTIGATOR)),
    session: Session = Depends(db_session),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    set_tenant(
        TenantContext(
            workspace_id=user.workspace_id, user_id=user.user_id, role=user.role
        )
    )
    inc = get_incident(session, incident_id)
    if inc is None:
        raise AppError(404, "Not Found", "Incident not found")

    inv_id = new_ulid()
    provider_name, model_id = settings.parse_model()
    inv = Investigation(
        id=inv_id,
        workspace_id=user.workspace_id,
        incident_id=incident_id,
        status="INVESTIGATING",
        model=f"{provider_name}:{model_id}",
        budget_usd=settings.default_budget_usd,
    )
    session.add(inv)
    session.flush()

    briefing: dict[str, Any] = {
        "suspects": [],
        "confidence": 0.0,
        "change_hits": [],
        "new_templates": [],
        "graph": [],
        "data_gaps": ["API started investigation without ingested briefing yet"],
        "timeline": [],
        "anomalies": [],
    }
    snippets: list[str] = []
    gaps: list[str] = []
    for ds_id in inc.dataset_ids or []:
        raw = dataset_dir(settings.data_dir, user.workspace_id, str(ds_id)) / "raw.log"
        if not raw.is_file():
            gaps.append(f"dataset {ds_id} missing raw.log")
            continue
        text = Path(raw).read_text(encoding="utf-8", errors="replace")
        snippets.append(text[:4000])
        briefing = briefing_from_log_text(text)
    if gaps:
        briefing["data_gaps"] = list(briefing.get("data_gaps") or []) + gaps

    gw = EgressGateway(
        no_external_llm=settings.no_external_llm or provider_name == "mock",
        allowlist_hosts=settings.model_allowlist_hosts(),
        budget_usd=settings.default_budget_usd,
    )
    result = run_investigation(
        briefing=briefing,
        gateway=gw,
        provider=MockProvider(briefing=briefing),
        model=model_id,
        budget=Budget(max_cost_usd=settings.default_budget_usd),
        untrusted_log_snippets=snippets,
    )

    steps_out: list[dict[str, Any]] = []
    for s in result.steps:
        row = InvestigationStep(
            id=new_ulid(),
            investigation_id=inv_id,
            seq=s.seq,
            kind=s.kind,
            name=s.name,
            args_json=s.args,
            tokens_in=s.tokens_in,
            tokens_out=s.tokens_out,
            cost_usd=s.cost_usd,
        )
        session.add(row)
        steps_out.append(
            {
                "seq": s.seq,
                "kind": s.kind,
                "name": s.name,
                "args": s.args,
            }
        )
    _STEP_CACHE[inv_id] = steps_out

    report_id = None
    if result.report is not None:
        report_id = new_ulid()
        session.add(
            Report(
                id=report_id,
                workspace_id=user.workspace_id,
                investigation_id=inv_id,
                json_body=result.report.model_dump(),
                markdown=_report_markdown(result.report),
                verification_json=result.verification,
            )
        )

    inv.status = result.status.value
    inv.outcome = result.status.value
    inv.spent_usd = result.spent_usd
    append_audit(
        session,
        workspace_id=user.workspace_id,
        actor=user.user_id,
        action="investigation.start",
        target=inv_id,
        detail={"incident_id": incident_id, "status": inv.status},
    )
    return {
        "id": inv_id,
        "status": inv.status,
        "report_id": report_id,
        "steps": len(steps_out),
    }


@router.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: str,
    user: AuthUser = Depends(require_role(Role.VIEWER)),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    inv = session.get(Investigation, investigation_id)
    if inv is None or inv.workspace_id != user.workspace_id:
        raise AppError(404, "Not Found", "Investigation not found")
    report = session.scalars(
        select(Report).where(Report.investigation_id == investigation_id)
    ).first()
    return {
        "id": inv.id,
        "incident_id": inv.incident_id,
        "status": inv.status,
        "model": inv.model,
        "outcome": inv.outcome,
        "spent_usd": inv.spent_usd,
        "report_id": report.id if report else None,
    }


@router.get("/investigations/{investigation_id}/events")
def investigation_events(
    investigation_id: str,
    after: int = 0,
    user: AuthUser = Depends(require_role(Role.VIEWER)),
    session: Session = Depends(db_session),
) -> StreamingResponse:
    inv = session.get(Investigation, investigation_id)
    if inv is None or inv.workspace_id != user.workspace_id:
        raise AppError(404, "Not Found", "Investigation not found")
    steps = _STEP_CACHE.get(investigation_id, [])
    return StreamingResponse(
        iter_steps_as_sse(steps, after=after),
        media_type="text/event-stream",
    )


@router.post("/investigations/{investigation_id}/cancel")
def cancel_investigation(
    investigation_id: str,
    user: AuthUser = Depends(require_role(Role.INVESTIGATOR)),
    session: Session = Depends(db_session),
) -> dict[str, str]:
    inv = session.get(Investigation, investigation_id)
    if inv is None or inv.workspace_id != user.workspace_id:
        raise AppError(404, "Not Found", "Investigation not found")
    inv.status = "CANCELLED"
    return {"id": inv.id, "status": inv.status}
