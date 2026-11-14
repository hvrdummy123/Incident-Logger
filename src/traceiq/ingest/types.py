"""Normalized telemetry event shapes used across parsers and the store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LogEvent:
    ts_ms: int | None
    service: str
    instance: str
    level: str
    message: str
    trace_id: str = ""
    span_id: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)
    source_file: str = ""
    line_no: int = 0
    template_id: str = ""
    raw: str = ""
    parse_ok: bool = True
    timestamp_inherited: bool = False


@dataclass(slots=True)
class DetectResult:
    format: str
    confidence: float
    samples_checked: int
    notes: str = ""
