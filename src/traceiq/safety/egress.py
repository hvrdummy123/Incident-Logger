"""Egress gateway — the only path that may call a model provider."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

from traceiq.safety.redact import RedactionMap, redact_text


class Provider(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]], *, model: str) -> dict[str, Any]: ...


@dataclass
class EgressRecord:
    provider: str
    model: str
    payload_sha256: str
    redaction_stats: dict[str, int]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    status: str
    blocked_reason: str | None = None


@dataclass
class EgressGateway:
    """Fails closed when NO_EXTERNAL_LLM is set; always redacts before send."""

    no_external_llm: bool
    allowlist_hosts: set[str]
    budget_usd: float
    spent_usd: float = 0.0
    ledger: list[EgressRecord] = field(default_factory=list)
    provider_base_urls: dict[str, str] = field(default_factory=dict)

    def _host_allowed(self, provider_name: str) -> bool:
        if provider_name == "mock":
            return True
        base = self.provider_base_urls.get(provider_name, "")
        if not base:
            # built-in known hosts checked via allowlist membership of canonical names
            return provider_name in {"anthropic", "openai"} and (
                "api.anthropic.com" in self.allowlist_hosts
                or "api.openai.com" in self.allowlist_hosts
                or "localhost" in self.allowlist_hosts
                or "127.0.0.1" in self.allowlist_hosts
            )
        host = (urlparse(base).hostname or "").lower()
        return host in self.allowlist_hosts

    def call(
        self,
        provider: Provider,
        *,
        model: str,
        messages: list[dict[str, str]],
        mapping: RedactionMap,
    ) -> dict[str, Any]:
        # Redact every message body before anything else
        redacted: list[dict[str, str]] = []
        stats: dict[str, int] = {}
        for msg in messages:
            rr = redact_text(msg.get("content", ""), mapping)
            for k, v in rr.stats.items():
                stats[k] = stats.get(k, 0) + v
            redacted.append({"role": msg["role"], "content": rr.text})

        payload = repr(redacted).encode()
        digest = hashlib.sha256(payload).hexdigest()

        if self.no_external_llm and provider.name != "mock":
            rec = EgressRecord(
                provider=provider.name,
                model=model,
                payload_sha256=digest,
                redaction_stats=stats,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=0,
                status="blocked",
                blocked_reason="NO_EXTERNAL_LLM",
            )
            self.ledger.append(rec)
            raise PermissionError("NO_EXTERNAL_LLM: external provider call blocked")

        if not self._host_allowed(provider.name):
            rec = EgressRecord(
                provider=provider.name,
                model=model,
                payload_sha256=digest,
                redaction_stats=stats,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=0,
                status="blocked",
                blocked_reason="host_not_allowlisted",
            )
            self.ledger.append(rec)
            raise PermissionError(f"provider host not allowlisted: {provider.name}")

        if self.spent_usd >= self.budget_usd:
            rec = EgressRecord(
                provider=provider.name,
                model=model,
                payload_sha256=digest,
                redaction_stats=stats,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=0,
                status="blocked",
                blocked_reason="budget_exhausted",
            )
            self.ledger.append(rec)
            raise PermissionError("investigation budget exhausted")

        # Prove no raw finding values remain in outbound payload
        blob = " ".join(m["content"] for m in redacted)
        for original in mapping.forward.values():
            if original and original in blob:
                raise RuntimeError("redaction failed: original secret present in egress payload")

        t0 = time.perf_counter()
        result = provider.complete(redacted, model=model)
        latency = int((time.perf_counter() - t0) * 1000)
        tokens_in = int(result.get("tokens_in", 0))
        tokens_out = int(result.get("tokens_out", 0))
        cost = float(result.get("cost_usd", 0.0))
        self.spent_usd += cost
        self.ledger.append(
            EgressRecord(
                provider=provider.name,
                model=model,
                payload_sha256=digest,
                redaction_stats=stats,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                latency_ms=latency,
                status="ok",
            )
        )
        return result
