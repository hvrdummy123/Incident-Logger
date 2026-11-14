"""Incident CRUD (tenant-scoped)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from traceiq.api.deps import AuthUser, db_session, require_role, settings_dep
from traceiq.api.errors import AppError
from traceiq.audit.chain import append_audit
from traceiq.auth.rbac import Role
from traceiq.config import Settings
from traceiq.db.models import Dataset, Incident
from traceiq.ids import new_ulid
from traceiq.store.datasets import dataset_dir, write_manifest
from traceiq.tenancy.scope import get_incident

router = APIRouter(prefix="/incidents", tags=["incidents"])


class CreateIncident(BaseModel):
    title: str
    severity: str = "sev3"
    window_start: datetime | None = None
    window_end: datetime | None = None
    dataset_ids: list[str] = Field(default_factory=list)
    source: str = "upload"
    # Optional BYO payload — stored under the workspace dataset sandbox.
    log_text: str | None = Field(default=None, max_length=40_000_000)
    filename: str = "upload.log"


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
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    dataset_ids = list(body.dataset_ids)
    if body.log_text:
        if "\x00" in body.log_text[:4096]:
            raise AppError(
                400,
                "Bad Request",
                "File looks binary. Upload a text log, or strip null bytes and retry.",
            )
        raw_hash = hashlib.sha256(body.log_text.encode("utf-8")).hexdigest()
        existing = session.scalar(
            select(Dataset).where(
                Dataset.workspace_id == user.workspace_id,
                Dataset.content_hash == raw_hash,
            )
        )
        if existing is not None:
            ds_id = existing.id
        else:
            ds_id = new_ulid()
            ds_path = dataset_dir(settings.data_dir, user.workspace_id, ds_id)
            (ds_path / "raw.log").write_text(body.log_text, encoding="utf-8")
            write_manifest(
                ds_path,
                {
                    "dataset_id": ds_id,
                    "workspace_id": user.workspace_id,
                    "filename": body.filename,
                    "content_hash": raw_hash,
                    "bytes": len(body.log_text.encode("utf-8")),
                },
            )
            session.add(
                Dataset(
                    id=ds_id,
                    workspace_id=user.workspace_id,
                    content_hash=raw_hash,
                    status="ready",
                    stats={"filename": body.filename, "bytes": len(body.log_text)},
                )
            )
        dataset_ids.append(ds_id)

    inc = Incident(
        id=new_ulid(),
        workspace_id=user.workspace_id,
        title=body.title,
        severity=body.severity,
        status="open",
        window_start=body.window_start,
        window_end=body.window_end,
        dataset_ids=dataset_ids,
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
        detail={"title": body.title, "dataset_ids": dataset_ids},
    )
    return {
        "id": inc.id,
        "title": inc.title,
        "severity": inc.severity,
        "status": inc.status,
        "source": inc.source,
        "dataset_ids": dataset_ids,
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
