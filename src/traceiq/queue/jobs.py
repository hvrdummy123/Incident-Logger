"""Postgres job queue using FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from traceiq.ids import new_ulid

DEFAULT_LEASE_SECONDS = 60
MAX_ATTEMPTS = 5


@dataclass
class ClaimedJob:
    id: str
    workspace_id: str | None
    kind: str
    payload: dict[str, Any]
    attempts: int


def enqueue(
    session: Session,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
    workspace_id: str | None = None,
    run_at: datetime | None = None,
) -> str:
    job_id = new_ulid()
    session.execute(
        text(
            """
            INSERT INTO jobs (id, workspace_id, kind, payload, status, attempts, run_at)
            VALUES (:id, :workspace_id, :kind, CAST(:payload AS jsonb), 'pending', 0, :run_at)
            """
        ),
        {
            "id": job_id,
            "workspace_id": workspace_id,
            "kind": kind,
            "payload": __import__("json").dumps(payload or {}),
            "run_at": run_at or datetime.now(UTC),
        },
    )
    return job_id


def claim_one(
    session: Session,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> ClaimedJob | None:
    now = now or datetime.now(UTC)
    locked_until = now + timedelta(seconds=lease_seconds)
    row = (
        session.execute(
            text(
                """
            UPDATE jobs
            SET status = 'running',
                locked_by = :worker_id,
                locked_until = :locked_until,
                attempts = attempts + 1
            WHERE id = (
              SELECT id FROM jobs
              WHERE status IN ('pending', 'running')
                AND run_at <= :now
                AND (locked_until IS NULL OR locked_until < :now)
                AND status <> 'dead'
                AND status <> 'done'
              ORDER BY run_at
              FOR UPDATE SKIP LOCKED
              LIMIT 1
            )
            RETURNING id, workspace_id, kind, payload, attempts
            """
            ),
            {"worker_id": worker_id, "locked_until": locked_until, "now": now},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = __import__("json").loads(payload)
    return ClaimedJob(
        id=row["id"],
        workspace_id=row["workspace_id"],
        kind=row["kind"],
        payload=payload or {},
        attempts=row["attempts"],
    )


def complete(session: Session, job_id: str) -> None:
    session.execute(
        text(
            """
            UPDATE jobs
            SET status = 'done', locked_by = NULL, locked_until = NULL, last_error = NULL
            WHERE id = :id
            """
        ),
        {"id": job_id},
    )


def fail(
    session: Session,
    job_id: str,
    error: str,
    *,
    now: datetime | None = None,
    backoff_base_seconds: float = 2.0,
) -> None:
    now = now or datetime.now(UTC)
    row = (
        session.execute(
            text("SELECT attempts FROM jobs WHERE id = :id"),
            {"id": job_id},
        )
        .mappings()
        .one()
    )
    attempts = int(row["attempts"])
    if attempts >= MAX_ATTEMPTS:
        session.execute(
            text(
                """
                UPDATE jobs
                SET status = 'dead', locked_by = NULL, locked_until = NULL, last_error = :error
                WHERE id = :id
                """
            ),
            {"id": job_id, "error": error[:4000]},
        )
        return
    delay = backoff_base_seconds**attempts
    session.execute(
        text(
            """
            UPDATE jobs
            SET status = 'pending',
                locked_by = NULL,
                locked_until = NULL,
                run_at = :run_at,
                last_error = :error
            WHERE id = :id
            """
        ),
        {
            "id": job_id,
            "run_at": now + timedelta(seconds=delay),
            "error": error[:4000],
        },
    )
