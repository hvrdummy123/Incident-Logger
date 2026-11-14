"""Incident CRUD (tenant-scoped)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from traceiq.api.deps import AuthUser, db_session, require_role
from traceiq.api.errors import AppError
from traceiq.audit.chain import append_audit
from traceiq.auth.rbac import Role
from traceiq.db.models import Incident
from traceiq.ids import new_ulid
from traceiq.tenancy.scope import get_incident

router = APIRouter(prefix="/incidents", tags=["incidents"])


class CreateIncident(BaseModel):
    title: str
    severity: str = "sev3"
    window_start: datetime | None = None
    window_end: datetime | None = None
    dataset_ids: list[str] = Field(default_factory=list)
    source: str = "upload"


@router.get("")
def list_incidents(
    user: AuthUser = Depends(require_role(Role.VIEWER)),
    session: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Incident).where(Incident.workspace_id == user.workspace_id)
    ).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "severity": r.severity,
            "status": r.status,
            "source": r.source,
        }
        for r in rows
    ]


@router.post("", status_code=201)
def create_incident(
    body: CreateIncident,
    user: AuthUser = Depends(require_role(Role.INVESTIGATOR)),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    inc = Incident(
        id=new_ulid(),
        workspace_id=user.workspace_id,
        title=body.title,
        severity=body.severity,
        status="open",
        window_start=body.window_start,
        window_end=body.window_end,
        dataset_ids=body.dataset_ids,
        source=body.source,
        created_by=user.user_id,
    )
    session.add(inc)
    session.flush()
    append_audit(
        session,
        workspace_id=user.workspace_id,
        actor=user.user_id,
        action="incident.create",
        target=inc.id,
        detail={"title": body.title},
    )
    return {
        "id": inc.id,
        "title": inc.title,
        "severity": inc.severity,
        "status": inc.status,
        "source": inc.source,
    }


@router.get("/{incident_id}")
def get_incident_route(
    incident_id: str,
    user: AuthUser = Depends(require_role(Role.VIEWER)),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    # App-layer scope (also RLS)
    from traceiq.tenancy.context import TenantContext, set_tenant

    set_tenant(
        TenantContext(
            workspace_id=user.workspace_id, user_id=user.user_id, role=user.role
        )
    )
    inc = get_incident(session, incident_id)
    if inc is None:
        raise AppError(404, "Not Found", "Incident not found")
    return {
        "id": inc.id,
        "title": inc.title,
        "severity": inc.severity,
        "status": inc.status,
        "dataset_ids": inc.dataset_ids,
        "source": inc.source,
    }
