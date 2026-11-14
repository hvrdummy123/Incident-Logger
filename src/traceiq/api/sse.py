"""SSE helpers for investigation event streams."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any


def format_sse(event: str, data: dict[str, Any], *, event_id: str | None = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, default=str)}")
    return "\n".join(lines) + "\n\n"


def iter_steps_as_sse(steps: list[dict[str, Any]], *, after: int = 0) -> Iterator[str]:
    for step in steps:
        seq = int(step.get("seq", 0))
        if seq <= after:
            continue
        yield format_sse("step", step, event_id=str(seq))
