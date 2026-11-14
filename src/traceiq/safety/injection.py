"""Detect prompt-injection-shaped lines in untrusted telemetry."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS = [
    re.compile(r"(?i)\bignore (all )?(previous|prior|above) instructions\b"),
    re.compile(r"(?i)\bdisregard (your|the) (system|safety) (prompt|rules)\b"),
    re.compile(r"(?i)^\s*(system|assistant|developer)\s*:"),
    re.compile(r"(?i)\byou are now\b.*\b(unrestricted|jailbroken|dan)\b"),
    re.compile(r"(?i)\b(exfiltrate|reveal|print) (the )?(api[_ ]?key|system prompt|secrets)\b"),
    re.compile(r"(?i)\btool[_ ]?result\b.*\{"),
    re.compile(r"(?i)\bcall (the )?(tool|function) (delete|drop|rm|wipe)\b"),
]


@dataclass(frozen=True, slots=True)
class InjectionHit:
    line: str
    pattern: str


def scan_for_injection(text: str) -> list[InjectionHit]:
    hits: list[InjectionHit] = []
    for line in text.splitlines():
        for pat in _PATTERNS:
            if pat.search(line):
                hits.append(InjectionHit(line=line[:500], pattern=pat.pattern))
                break
    return hits


def injection_suspected(texts: list[str]) -> bool:
    return any(scan_for_injection(t) for t in texts)
