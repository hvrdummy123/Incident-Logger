"""Format auto-detection by sampling lines."""

from __future__ import annotations

import json
import random
from pathlib import Path

from traceiq.ingest.parsers.logs import PARSERS, parse_line
from traceiq.ingest.types import DetectResult

_ORDER = ("jsonl", "cri", "nginx", "logfmt", "syslog", "plain")


def _sample_lines(path: Path, head: int = 40, mid: int = 20, seed: int = 0) -> list[str]:
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= head:
                break
            lines.append(line.rstrip("\n"))
    # optional mid-file sample for longer files
    try:
        size = path.stat().st_size
    except OSError:
        return lines
    if size < 8_000:
        return lines
    rng = random.Random(seed)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(rng.randint(0, max(0, size - 2000)))
        f.readline()  # align
        for _ in range(mid):
            line = f.readline()
            if not line:
                break
            lines.append(line.rstrip("\n"))
    return lines


def detect_format(path: Path, *, seed: int = 0) -> DetectResult:
    samples = [ln for ln in _sample_lines(path, seed=seed) if ln.strip()]
    if not samples:
        return DetectResult(format="plain", confidence=0.0, samples_checked=0, notes="empty")

    scores: dict[str, int] = {k: 0 for k in _ORDER}
    for line in samples:
        # cheap json peek
        if line.startswith("{") and line.endswith("}"):
            try:
                json.loads(line)
                scores["jsonl"] += 2
            except json.JSONDecodeError:
                pass
        for fmt in _ORDER:
            ev = parse_line(line, fmt)
            if ev.parse_ok:
                scores[fmt] += 1

    best = max(_ORDER, key=lambda f: scores[f])
    total = max(1, len(samples))
    confidence = min(1.0, scores[best] / total)
    return DetectResult(
        format=best,
        confidence=confidence,
        samples_checked=len(samples),
        notes=", ".join(f"{k}={scores[k]}" for k in _ORDER),
    )


def detect_or_override(path: Path, override: str | None = None, *, seed: int = 0) -> DetectResult:
    if override:
        if override not in PARSERS:
            raise ValueError(f"unknown format: {override}")
        return DetectResult(format=override, confidence=1.0, samples_checked=0, notes="override")
    return detect_format(path, seed=seed)
