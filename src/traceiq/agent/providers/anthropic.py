"""Anthropic adapter — only imported/used via the egress gateway."""

from __future__ import annotations

from typing import Any


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None, **_: Any) -> None:
        self.api_key = api_key
        # NOTE: real HTTP client wired when a key is present; M7 keeps the seam.

    def complete(self, messages: list[dict[str, str]], *, model: str) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        raise NotImplementedError("live Anthropic calls not enabled in this build yet")
