"""Simple worker loop — claim jobs and dispatch by kind."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from traceiq.queue.jobs import ClaimedJob, claim_one, complete, fail

log = logging.getLogger(__name__)

Handler = Callable[[Session, ClaimedJob], None]


def run_once(
    session: Session,
    *,
    worker_id: str,
    handlers: dict[str, Handler],
    backoff_base_seconds: float = 2.0,
) -> bool:
    """Process at most one job. Returns True if a job was claimed."""
    job = claim_one(session, worker_id=worker_id)
    if job is None:
        return False
    # Persist the lease + attempt bump before work, otherwise a handler
    # exception + rollback would undo the claim and we'd never dead-letter.
    session.commit()

    handler = handlers.get(job.kind)
    if handler is None:
        fail(
            session,
            job.id,
            f"unknown job kind: {job.kind}",
            backoff_base_seconds=backoff_base_seconds,
        )
        session.commit()
        return True
    try:
        handler(session, job)
        complete(session, job.id)
        session.commit()
    except Exception as e:  # noqa: BLE001 — worker must not die on one bad job
        session.rollback()
        fail(
            session,
            job.id,
            f"{e.__class__.__name__}: {e}",
            backoff_base_seconds=backoff_base_seconds,
        )
        session.commit()
        log.exception("job %s failed", job.id)
    return True


def run_forever(
    session_factory: Callable[[], Session],
    *,
    worker_id: str,
    handlers: dict[str, Handler],
    idle_sleep: float = 0.5,
    stop_flag: dict[str, Any] | None = None,
) -> None:
    stop_flag = stop_flag or {"stop": False}
    while not stop_flag.get("stop"):
        session = session_factory()
        try:
            worked = run_once(session, worker_id=worker_id, handlers=handlers)
        finally:
            session.close()
        if not worked:
            time.sleep(idle_sleep)
