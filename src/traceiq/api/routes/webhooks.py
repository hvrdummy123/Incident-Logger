"""Alert webhook intake (API-key auth, idempotency)."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from traceiq.api.deps import db_session
from traceiq.api.errors import AppError
from traceiq.audit.chain import append_audit
from traceiq.db.models import ApiKey, Incident
from traceiq.ids import new_ulid

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Tiny in-process idempotency cache for M8; durable store later.
_SEEN_KEYS: set[str] = set()


class AlertBody(BaseModel):
    title: str = "alert"
    severity: str = "sev3"
    labels: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)


@router.post("/alerts", status_code=201)
def alert_webhook(
    body: AlertBody,
    session: Session = Depends(db_session),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not x_api_key or not x_workspace_id:
        raise AppError(401, "Unauthorized", "X-API-Key and X-Workspace-Id required")
    if len(body.model_dump_json()) > 100_000:
        raise AppError(413, "Payload Too Large", "Webhook body exceeds limit")

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    # Look up without RLS first via admin path — api_keys is RLS-scoped; set workspace
    from sqlalchemy import text

    session.execute(
        text("SELECT set_config('app.workspace_id', :wid, true)"),
        {"wid": x_workspace_id},
    )
    row = session.scalar(
        select(ApiKey).where(
            ApiKey.workspace_id == x_workspace_id,
            ApiKey.key_hash == key_hash,
            ApiKey.revoked_at.is_(None),
        )
    )
    if row is None:
        raise AppError(401, "Unauthorized", "Invalid API key")

    if idempotency_key:
        cache_key = f"{x_workspace_id}:{idempotency_key}"
        if cache_key in _SEEN_KEYS:
            return {"status": "duplicate", "idempotency_key": idempotency_key}
        _SEEN_KEYS.add(cache_key)

    inc = Incident(
        id=new_ulid(),
        workspace_id=x_workspace_id,
        title=body.title,
        severity=body.severity,
        status="open",
        dataset_ids=[],
        source="webhook",
    )
    session.add(inc)
    session.flush()
    append_audit(
        session,
        workspace_id=x_workspace_id,
        actor=f"api_key:{row.id}",
        action="webhook.alert",
        target=inc.id,
        detail={"title": body.title},
    )
    return {"incident_id": inc.id, "status": "created"}
