"""Redact findings to stable per-investigation placeholders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from traceiq.safety.detectors import Finding, find_secrets


@dataclass
class RedactionMap:
    """placeholder -> original value (kept only for authorized reveal)."""

    investigation_id: str
    forward: dict[str, str] = field(default_factory=dict)  # placeholder -> value
    reverse: dict[str, str] = field(default_factory=dict)  # value -> placeholder
    counts: dict[str, int] = field(default_factory=dict)

    def placeholder_for(self, kind: str, value: str) -> str:
        if value in self.reverse:
            return self.reverse[value]
        n = self.counts.get(kind, 0) + 1
        self.counts[kind] = n
        ph = f"<{kind.upper()}_{n}>"
        self.forward[ph] = value
        self.reverse[value] = ph
        return ph


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    findings: list[Finding]
    stats: dict[str, int]


def redact_text(
    text: str,
    mapping: RedactionMap,
    *,
    custom_findings: list[Finding] | None = None,
) -> RedactionResult:
    findings = custom_findings if custom_findings is not None else find_secrets(text)
    if not findings:
        return RedactionResult(text=text, findings=[], stats={})

    # Replace from the end so offsets stay valid
    out = text
    stats: dict[str, int] = {}
    for f in sorted(findings, key=lambda x: x.start, reverse=True):
        ph = mapping.placeholder_for(f.kind, f.value)
        out = out[: f.start] + ph + out[f.end :]
        stats[f.kind] = stats.get(f.kind, 0) + 1
    return RedactionResult(text=out, findings=findings, stats=stats)


def redaction_preview(text: str, investigation_id: str = "preview") -> dict[str, Any]:
    mapping = RedactionMap(investigation_id=investigation_id)
    result = redact_text(text, mapping)
    examples = [
        {
            "kind": f.kind,
            "placeholder": mapping.reverse.get(f.value, ""),
            "sample": f.value[:4] + "…",
        }
        for f in result.findings[:10]
    ]
    return {
        "stats": result.stats,
        "examples": examples,
        "redacted_preview": result.text[:2000],
    }
