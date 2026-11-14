"""OpenAI-compatible adapter (also covers local Ollama/vLLM via base_url)."""

from __future__ import annotations

from typing import Any


class OpenAICompatProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, **_: Any) -> None:
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"

    def complete(self, messages: list[dict[str, str]], *, model: str) -> dict[str, Any]:
        if not self.api_key and "localhost" not in (self.base_url or ""):
            raise RuntimeError("OpenAI API key not configured")
        raise NotImplementedError("live OpenAI-compat calls not enabled in this build yet")
