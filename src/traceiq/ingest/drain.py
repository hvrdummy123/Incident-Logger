"""Drain-style template mining — fixed-depth prefix tree, implemented here (not vendored)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# Mask high-cardinality tokens before clustering.
_UUID = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
_MASKS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(_UUID), "<*>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<*>"),
    (re.compile(r"\b[0-9a-fA-F]{16,}\b"), "<*>"),
    (re.compile(r"\b\d+(?:\.\d+)?(ms|s|us|ns|%)\b"), "<*>"),
    (re.compile(r"(/[^\s:]+)+"), "<*>"),
    (re.compile(r"\b\d+\b"), "<*>"),
    (re.compile(r"'[^']*'|\"[^\"]*\""), "<*>"),
]


def mask_message(msg: str) -> str:
    out = msg
    for pat, repl in _MASKS:
        out = pat.sub(repl, out)
    return out


def tokenize(msg: str) -> list[str]:
    return mask_message(msg).split()


@dataclass
class _Node:
    children: dict[str, _Node] = field(default_factory=dict)
    templates: list[list[str]] = field(default_factory=list)


@dataclass
class Template:
    template_id: str
    service: str
    pattern: str
    example_message: str
    count: int = 0


class Drain:
    """Per-service Drain with depth and similarity threshold."""

    def __init__(self, *, depth: int = 4, sim_threshold: float = 0.5) -> None:
        self.depth = max(1, depth)
        self.sim_threshold = sim_threshold
        self._trees: dict[str, dict[int, _Node]] = {}
        self._templates: dict[str, Template] = {}

    def _sim(self, a: list[str], b: list[str]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        same = sum(1 for x, y in zip(a, b, strict=True) if x == y)
        return same / len(a)

    def _merge(self, a: list[str], b: list[str]) -> list[str]:
        return [x if x == y else "<*>" for x, y in zip(a, b, strict=True)]

    def _tid(self, service: str, pattern_tokens: list[str]) -> str:
        body = service + "\0" + " ".join(pattern_tokens)
        return "tpl_" + hashlib.sha256(body.encode()).hexdigest()[:16]

    def add(self, service: str, message: str) -> str:
        tokens = tokenize(message)
        length = len(tokens)
        roots = self._trees.setdefault(service, {})
        node = roots.setdefault(length, _Node())

        # Walk by leading tokens up to depth-1 (Drain paper style).
        for i in range(min(self.depth - 1, length)):
            key = tokens[i] if tokens[i] != "<*>" else "<*>"
            node = node.children.setdefault(key, _Node())

        best_idx = -1
        best_sim = -1.0
        for i, tpl in enumerate(node.templates):
            # Never merge different token counts (also keyed by length above).
            if len(tpl) != length:
                continue
            s = self._sim(tpl, tokens)
            if s > best_sim:
                best_sim = s
                best_idx = i

        if best_idx >= 0 and best_sim >= self.sim_threshold:
            merged = self._merge(node.templates[best_idx], tokens)
            node.templates[best_idx] = merged
            pattern = " ".join(merged)
        else:
            node.templates.append(list(tokens))
            pattern = " ".join(tokens)

        tid = self._tid(service, pattern.split())
        existing = self._templates.get(tid)
        if existing is None:
            self._templates[tid] = Template(
                template_id=tid,
                service=service,
                pattern=pattern,
                example_message=message,
                count=1,
            )
        else:
            existing.count += 1
            existing.pattern = pattern
        return tid

    def templates(self) -> list[Template]:
        return list(self._templates.values())
