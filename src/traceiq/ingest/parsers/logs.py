"""Log line parsers — one module, plain functions, no parser-framework ceremony."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from traceiq.ingest.limits import truncate_line
from traceiq.ingest.normalize import (
    LEVEL_KEYS,
    MSG_KEYS,
    SERVICE_KEYS,
    TS_KEYS,
    as_str,
    normalize_level,
    parse_timestamp,
    pick,
)
from traceiq.ingest.types import LogEvent

# nginx/apache combined
_COMBINED = re.compile(
    r"^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] \"(?P<req>[^\"]*)\" "
    r"(?P<status>\d{3}) (?P<size>\S+)"
    r"(?: \"(?P<ref>[^\"]*)\" \"(?P<ua>[^\"]*)\")?"
)

# CRI: <time> <stream> <flag> <message>
_CRI = re.compile(
    r"^(?P<time>\S+)\s+(?P<stream>stdout|stderr)\s+(?P<flag>[FP])\s+(?P<msg>.*)$"
)

# syslog RFC5424-ish / 3164-ish
_SYSLOG = re.compile(
    r"^<?(?P<pri>\d{1,3})?>?(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}T\S+)\s+"
    r"(?P<host>\S+)\s+(?P<tag>[^:\s]+)(?::\s*|\s+)(?P<msg>.*)$"
)

_PLAIN_TS = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?P<rest>.*)$"
)

_STACK_START = re.compile(
    r"(Exception|Error|Traceback \(most recent call last\):|Caused by:)",
    re.I,
)
_STACK_CONT = re.compile(
    r"^(\s+at |\s+File |\s+\.\.\.|\s{2,}|Caused by:|\w+(Error|Exception|Warning):)"
)


def _base(
    *,
    ts_ms: int | None,
    service: str,
    level: str,
    message: str,
    raw: str,
    line_no: int,
    source_file: str,
    attrs: dict[str, Any] | None = None,
    instance: str = "",
    ok: bool = True,
) -> LogEvent:
    return LogEvent(
        ts_ms=ts_ms,
        service=service or "unknown",
        instance=instance,
        level=normalize_level(level),
        message=message,
        attrs=attrs or {},
        source_file=source_file,
        line_no=line_no,
        raw=raw,
        parse_ok=ok,
    )


def parse_jsonl(
    line: str,
    *,
    line_no: int = 0,
    source_file: str = "",
) -> LogEvent:
    line, _ = truncate_line(line)
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return _base(
            ts_ms=None,
            service="unknown",
            level="INFO",
            message=line,
            raw=line,
            line_no=line_no,
            source_file=source_file,
            ok=False,
        )
    if not isinstance(obj, dict):
        return _base(
            ts_ms=None,
            service="unknown",
            level="INFO",
            message=line,
            raw=line,
            line_no=line_no,
            source_file=source_file,
            ok=False,
        )
    ts = parse_timestamp(pick(obj, TS_KEYS))
    msg = as_str(pick(obj, MSG_KEYS), line)
    level = as_str(pick(obj, LEVEL_KEYS), "INFO")
    service = as_str(pick(obj, SERVICE_KEYS), "unknown")
    return _base(
        ts_ms=ts,
        service=service,
        level=level,
        message=msg,
        raw=line,
        line_no=line_no,
        source_file=source_file,
        attrs={k: v for k, v in obj.items() if k not in TS_KEYS + MSG_KEYS + LEVEL_KEYS},
        instance=as_str(obj.get("instance") or obj.get("host") or ""),
    )


def parse_logfmt(line: str, *, line_no: int = 0, source_file: str = "") -> LogEvent:
    line, _ = truncate_line(line)
    fields: dict[str, str] = {}
    for m in re.finditer(r'([^\s=]+)=("([^"\\]|\\.)*"|[^\s]+)', line):
        k, v = m.group(1), m.group(2)
        if v.startswith('"') and v.endswith('"'):
            v = bytes(v[1:-1], "utf-8").decode("unicode_escape", errors="replace")
        fields[k] = v
    if not fields:
        return _base(
            ts_ms=None,
            service="unknown",
            level="INFO",
            message=line,
            raw=line,
            line_no=line_no,
            source_file=source_file,
            ok=False,
        )
    return _base(
        ts_ms=parse_timestamp(pick(fields, TS_KEYS)),
        service=as_str(pick(fields, SERVICE_KEYS), "unknown"),
        level=as_str(pick(fields, LEVEL_KEYS), "INFO"),
        message=as_str(pick(fields, MSG_KEYS), line),
        raw=line,
        line_no=line_no,
        source_file=source_file,
        attrs=fields,
    )


def parse_nginx(line: str, *, line_no: int = 0, source_file: str = "") -> LogEvent:
    line, _ = truncate_line(line)
    m = _COMBINED.match(line)
    if not m:
        return _base(
            ts_ms=None,
            service="nginx",
            level="INFO",
            message=line,
            raw=line,
            line_no=line_no,
            source_file=source_file,
            ok=False,
        )
    # 10/Oct/2024:12:00:00 +0000
    t = m.group("time").split()[0]
    ts = parse_timestamp(t.replace(":", " ", 1)) if t else None
    status = int(m.group("status"))
    level = "ERROR" if status >= 500 else "WARN" if status >= 400 else "INFO"
    return _base(
        ts_ms=ts,
        service="nginx",
        level=level,
        message=m.group("req"),
        raw=line,
        line_no=line_no,
        source_file=source_file,
        attrs={"status": status, "ip": m.group("ip"), "size": m.group("size")},
    )


def parse_cri(line: str, *, line_no: int = 0, source_file: str = "") -> LogEvent:
    line, _ = truncate_line(line)
    m = _CRI.match(line)
    if not m:
        return _base(
            ts_ms=None,
            service="unknown",
            level="INFO",
            message=line,
            raw=line,
            line_no=line_no,
            source_file=source_file,
            ok=False,
        )
    level = "ERROR" if m.group("stream") == "stderr" else "INFO"
    return _base(
        ts_ms=parse_timestamp(m.group("time")),
        service="unknown",
        level=level,
        message=m.group("msg"),
        raw=line,
        line_no=line_no,
        source_file=source_file,
        attrs={"stream": m.group("stream"), "flag": m.group("flag")},
    )


def parse_syslog(line: str, *, line_no: int = 0, source_file: str = "") -> LogEvent:
    line, _ = truncate_line(line)
    m = _SYSLOG.match(line)
    if not m:
        return _base(
            ts_ms=None,
            service="unknown",
            level="INFO",
            message=line,
            raw=line,
            line_no=line_no,
            source_file=source_file,
            ok=False,
        )
    level = "INFO"
    if m.group("pri"):
        sev = int(m.group("pri")) % 8
        level = str(sev)
    return _base(
        ts_ms=parse_timestamp(m.group("ts")),
        service=m.group("tag"),
        level=level,
        message=m.group("msg"),
        raw=line,
        line_no=line_no,
        source_file=source_file,
        instance=m.group("host"),
    )


def parse_plain(line: str, *, line_no: int = 0, source_file: str = "") -> LogEvent:
    line, _ = truncate_line(line)
    m = _PLAIN_TS.match(line)
    if not m:
        return _base(
            ts_ms=None,
            service="unknown",
            level="INFO",
            message=line,
            raw=line,
            line_no=line_no,
            source_file=source_file,
            ok=False,
        )
    return _base(
        ts_ms=parse_timestamp(m.group("ts")),
        service="unknown",
        level="INFO",
        message=m.group("rest"),
        raw=line,
        line_no=line_no,
        source_file=source_file,
    )


PARSERS = {
    "jsonl": parse_jsonl,
    "logfmt": parse_logfmt,
    "nginx": parse_nginx,
    "cri": parse_cri,
    "syslog": parse_syslog,
    "plain": parse_plain,
}


def parse_line(
    line: str,
    fmt: str,
    *,
    line_no: int = 0,
    source_file: str = "",
) -> LogEvent:
    fn = PARSERS.get(fmt, parse_plain)
    return fn(line, line_no=line_no, source_file=source_file)


def group_stacktraces(lines: list[str]) -> list[str]:
    """Merge multi-line Java/Python stack traces into single logical lines."""
    out: list[str] = []
    buf: list[str] = []
    for line in lines:
        if buf and _STACK_CONT.match(line):
            buf.append(line)
            continue
        if buf:
            out.append("\n".join(buf))
            buf = []
        if _STACK_START.search(line):
            buf = [line]
        else:
            out.append(line)
    if buf:
        out.append("\n".join(buf))
    return out


def iter_parsed(
    lines: Iterator[str] | list[str],
    fmt: str,
    *,
    source_file: str = "",
    group_stacks: bool = True,
) -> Iterator[LogEvent]:
    material = list(lines)
    maybe_stacks = group_stacks and fmt in {"plain", "jsonl", "cri"}
    if maybe_stacks and any(_STACK_START.search(x) for x in material[:50]):
        material = group_stacktraces(material)
    prev_ts: int | None = None
    for i, line in enumerate(material, start=1):
        if not line.strip():
            continue
        ev = parse_line(line.rstrip("\n"), fmt, line_no=i, source_file=source_file)
        if ev.ts_ms is None and prev_ts is not None:
            ev.ts_ms = prev_ts
            ev.timestamp_inherited = True
        if ev.ts_ms is not None:
            prev_ts = ev.ts_ms
        yield ev
