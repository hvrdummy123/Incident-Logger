"""Worker process entrypoint."""

from __future__ import annotations

import logging
import os
import signal
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from traceiq.db.session import get_session_factory
from traceiq.queue.jobs import ClaimedJob
from traceiq.queue.worker import run_forever

log = logging.getLogger("traceiq.worker")

Handler = Callable[[Session, ClaimedJob], None]


def _noop_handlers() -> dict[str, Handler]:
    # Handlers for specific kinds land as jobs are enqueued from the API.
    # Unknown kinds still dead-letter via run_once.
    return {}


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("TRACEIQ_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker_id = os.environ.get("TRACEIQ_WORKER_ID") or f"worker-{uuid.uuid4().hex[:8]}"
    stop: dict[str, bool] = {"stop": False}

    def _stop(*_args: object) -> None:
        log.info("shutdown requested")
        stop["stop"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    log.info("worker starting id=%s", worker_id)
    run_forever(
        get_session_factory(),
        worker_id=worker_id,
        handlers=_noop_handlers(),
        stop_flag=stop,
    )
    log.info("worker stopped")


if __name__ == "__main__":
    main()
