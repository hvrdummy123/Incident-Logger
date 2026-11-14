"""Admin audit + egress ledger views."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from traceiq.api.deps import AuthUser, db_session, require_role
from traceiq.audit.chain import verify_chain
from traceiq.auth.rbac import Role
from traceiq.db.models import AuditLog, ModelCall

router = APIRouter(tags=["admin"])


@router.get("/audit")
def get_audit(
    user: AuthUser = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    rows = session.scalars(
        select(AuditLog)
        .where(AuditLog.workspace_id == user.workspace_id)
        .order_by(AuditLog.seq.asc())
        .limit(200)
    ).all()
    verified = verify_chain(session, user.workspace_id)
    return {
        "chain": {
            "ok": verified.ok,
            "checked": verified.checked,
            "first_break_seq": verified.first_break_seq,
            "reason": verified.reason,
        },
        "entries": [
            {
                "seq": r.seq,
                "ts": r.ts.isoformat() if r.ts else None,
                "actor": r.actor,
                "action": r.action,
                "target": r.target,
            }
            for r in rows
        ],
    }


@router.get("/egress-ledger")
def egress_ledger(
    user: AuthUser = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ModelCall)
        .where(ModelCall.workspace_id == user.workspace_id)
        .order_by(ModelCall.created_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "id": r.id,
            "provider": r.provider,
            "model": r.model,
            "payload_sha256": r.payload_sha256,
            "status": r.status,
            "cost_usd": r.cost_usd,
            "redaction_stats": r.redaction_stats_json,
        }
        for r in rows
    ]
