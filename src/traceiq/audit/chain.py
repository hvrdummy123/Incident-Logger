"""Hash-chained append-only audit log per workspace."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from traceiq.db.models import AuditLog
from traceiq.ids import new_ulid

GENESIS = "0" * 64


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, record: dict[str, Any]) -> str:
    payload = prev_hash + _canonical(record)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuditAppend:
    id: str
    seq: int
    hash: str


def append_audit(
    session: Session,
    *,
    workspace_id: str,
    actor: str,
    action: str,
    target: str = "",
    detail: dict[str, Any] | None = None,
    ts: datetime | None = None,
) -> AuditAppend:
    detail = detail or {}
    ts = ts or datetime.now(UTC)

    last = session.execute(
        select(AuditLog)
        .where(AuditLog.workspace_id == workspace_id)
        .order_by(AuditLog.seq.desc())
        .limit(1)
    ).scalar_one_or_none()

    prev_hash = last.hash if last else GENESIS
    seq = (last.seq + 1) if last else 1
    body = {
        "workspace_id": workspace_id,
        "seq": seq,
        "ts": ts.isoformat(),
        "actor": actor,
        "action": action,
        "target": target,
        "detail": detail,
    }
    digest = compute_hash(prev_hash, body)
    row = AuditLog(
        id=new_ulid(),
        workspace_id=workspace_id,
        seq=seq,
        ts=ts,
        actor=actor,
        action=action,
        target=target,
        detail_json=detail,
        prev_hash=prev_hash,
        hash=digest,
    )
    session.add(row)
    session.flush()
    return AuditAppend(id=row.id, seq=seq, hash=digest)


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    checked: int
    first_break_seq: int | None
    reason: str | None


def verify_chain(session: Session, workspace_id: str) -> VerifyResult:
    rows = (
        session.execute(
            select(AuditLog)
            .where(AuditLog.workspace_id == workspace_id)
            .order_by(AuditLog.seq.asc())
        )
        .scalars()
        .all()
    )
    if not rows:
        return VerifyResult(ok=True, checked=0, first_break_seq=None, reason=None)

    expected_prev = GENESIS
    expected_seq = 1
    for row in rows:
        if row.seq != expected_seq:
            return VerifyResult(
                ok=False,
                checked=expected_seq - 1,
                first_break_seq=row.seq,
                reason=f"sequence gap: expected {expected_seq}, got {row.seq}",
            )
        if row.prev_hash != expected_prev:
            return VerifyResult(
                ok=False,
                checked=expected_seq - 1,
                first_break_seq=row.seq,
                reason="prev_hash mismatch",
            )
        body = {
            "workspace_id": row.workspace_id,
            "seq": row.seq,
            "ts": row.ts.isoformat(),
            "actor": row.actor,
            "action": row.action,
            "target": row.target,
            "detail": row.detail_json,
        }
        digest = compute_hash(row.prev_hash, body)
        if digest != row.hash:
            return VerifyResult(
                ok=False,
                checked=expected_seq - 1,
                first_break_seq=row.seq,
                reason="hash mismatch",
            )
        expected_prev = row.hash
        expected_seq += 1

    return VerifyResult(ok=True, checked=len(rows), first_break_seq=None, reason=None)
