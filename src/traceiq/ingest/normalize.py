"""Field aliasing and timestamp coercion."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

LEVEL_MAP = {
    "trace": "TRACE",
    "debug": "DEBUG",
    "info": "INFO",
    "information": "INFO",
    "warn": "WARN",
    "warning": "WARN",
    "error": "ERROR",
    "err": "ERROR",
    "fatal": "FATAL",
    "critical": "FATAL",
    "crit": "FATAL",
    "panic": "FATAL",
}

TS_KEYS = ("ts", "time", "timestamp", "@timestamp", "datetime", "date")
MSG_KEYS = ("msg", "message", "log", "text", "body")
LEVEL_KEYS = ("level", "severity", "lvl", "log.level")
SERVICE_KEYS = (
    "service",
    "app",
    "container",
    "kubernetes.container_name",
    "service.name",
)


def pick(d: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
        # dotted path
        if "." in k:
            cur: Any = d
            ok = True
            for part in k.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    ok = False
                    break
                cur = cur[part]
            if ok and cur is not None:
                return cur
    return None


def normalize_level(raw: Any) -> str:
    if raw is None:
        return "INFO"
    s = str(raw).strip().lower()
    if s.isdigit():
        # syslog severity 0-7
        n = int(s)
        return ["FATAL", "FATAL", "CRIT", "ERROR", "WARN", "INFO", "INFO", "DEBUG"][min(n, 7)]
    return LEVEL_MAP.get(s, s.upper()[:16] or "INFO")


def parse_timestamp(value: Any, *, default_tz: str = "UTC") -> int | None:
    """Return epoch milliseconds, or None if unparseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        # heuristic: ns / us / ms / s
        if v > 1e17:  # ns
            return int(v / 1e6)
        if v > 1e14:  # us
            return int(v / 1e3)
        if v > 1e11:  # ms
            return int(v)
        return int(v * 1000)

    s = str(value).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return parse_timestamp(float(s))

    # ISO-8601 — tolerate trailing Z
    s2 = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d/%b/%Y:%H:%M:%S",
        "%b %d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s[:26], fmt).replace(tzinfo=UTC)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return None


def as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)
