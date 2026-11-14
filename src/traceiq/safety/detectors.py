"""PII / secret detectors. Patterns are intentionally boring and explicit."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Finding:
    kind: str
    start: int
    end: int
    value: str


def _luhn_ok(num: str) -> bool:
    digits = [int(c) for c in num if c.isdigit()]
    if len(digits) < 13:
        return False
    s = 0
    alt = False
    for d in reversed(digits):
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        s += d
        alt = not alt
    return s % 10 == 0


def _verhoeff_ok(num: str) -> bool:
    # Compact Verhoeff for Aadhaar-shaped checks
    d_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    ]
    p_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
    ]
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = d_table[c][p_table[i % 8][int(ch)]]
    return c == 0


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (
        "ipv4",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
    ),
    (
        "ipv6",
        re.compile(
            r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
            r"|\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b"
        ),
    ),
    ("phone", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
            r"[\s\S]+?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ),
    ("url_creds", re.compile(r"https?://[^/\s:]+:[^/\s@]+@[^\s]+")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    ("pan_in", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("aadhaar", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
]


def find_secrets(text: str) -> list[Finding]:
    found: list[Finding] = []
    for kind, pat in _PATTERNS:
        for m in pat.finditer(text):
            val = m.group(0)
            if kind == "card":
                digits = re.sub(r"\D", "", val)
                if not _luhn_ok(digits):
                    continue
            if kind == "aadhaar":
                digits = re.sub(r"\D", "", val)
                if len(digits) != 12 or not _verhoeff_ok(digits):
                    continue
            if kind == "iban" and not _iban_ok(val):
                continue
            found.append(Finding(kind=kind, start=m.start(), end=m.end(), value=val))
    # high-entropy-ish tokens (length + charset heuristic)
    for m in re.finditer(r"\b[A-Za-z0-9_\-/+]{32,}\b", text):
        val = m.group(0)
        if any(f.start <= m.start() < f.end for f in found):
            continue
        classes = sum(
            [
                any(c.islower() for c in val),
                any(c.isupper() for c in val),
                any(c.isdigit() for c in val),
                any(c in "-_/+=" for c in val),
            ]
        )
        if classes >= 3:
            found.append(Finding(kind="secret", start=m.start(), end=m.end(), value=val))
    found.sort(key=lambda f: (f.start, -(f.end - f.start)))
    return _dedupe_overlaps(found)


def _iban_ok(iban: str) -> bool:
    s = iban.replace(" ", "").upper()
    if len(s) < 15:
        return False
    rearr = s[4:] + s[:4]
    nums = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearr)
    try:
        return int(nums) % 97 == 1
    except ValueError:
        return False


def _dedupe_overlaps(findings: list[Finding]) -> list[Finding]:
    out: list[Finding] = []
    last_end = -1
    for f in findings:
        if f.start < last_end:
            continue
        out.append(f)
        last_end = f.end
    return out
