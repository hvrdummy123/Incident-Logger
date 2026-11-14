"""Reports and feedback."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from traceiq.api.deps import AuthUser, db_session, require_role
from traceiq.api.errors import AppError
from traceiq.audit.chain import append_audit
from traceiq.auth.rbac import Role
from traceiq.db.models import Feedback, Report
from traceiq.ids import new_ulid

router = APIRouter(prefix="/reports", tags=["reports"])


class FeedbackBody(BaseModel):
    verdict: Literal["correct", "partially", "wrong"]
    true_root_cause: str | None = None
    notes: str = ""


@router.get("/{report_id}")
def get_report(
    report_id: str,
    request: Request,
    user: AuthUser = Depends(require_role(Role.VIEWER)),
    session: Session = Depends(db_session),
) -> Response:
    rep = session.get(Report, report_id)
    if rep is None or rep.workspace_id != user.workspace_id:
        raise AppError(404, "Not Found", "Report not found")
    accept = request.headers.get("accept", "application/json")
    if "text/markdown" in accept:
        return PlainTextResponse(rep.markdown, media_type="text/markdown")
    return JSONResponse(
        {
            "id": rep.id,
            "investigation_id": rep.investigation_id,
            "json": rep.json_body,
            "verification": rep.verification_json,
        }
    )


@router.post("/{report_id}/feedback", status_code=201)
def submit_feedback(
    report_id: str,
    body: FeedbackBody,
    user: AuthUser = Depends(require_role(Role.INVESTIGATOR)),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    rep = session.get(Report, report_id)
    if rep is None or rep.workspace_id != user.workspace_id:
        raise AppError(404, "Not Found", "Report not found")
    fb = Feedback(
        id=new_ulid(),
        report_id=report_id,
        verdict=body.verdict,
        true_root_cause=body.true_root_cause,
        notes=body.notes,
        user_id=user.user_id,
    )
    session.add(fb)
    append_audit(
        session,
        workspace_id=user.workspace_id,
        actor=user.user_id,
        action="report.feedback",
        target=report_id,
        detail={"verdict": body.verdict},
    )
    return {"id": fb.id, "verdict": fb.verdict}
