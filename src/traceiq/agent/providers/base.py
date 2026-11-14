"""Provider registry — no model IDs hardcoded in call sites."""

from __future__ import annotations

from typing import Any

from traceiq.agent.providers.mock import MockProvider


def get_provider(provider: str, **kwargs: Any) -> Any:
    if provider == "mock":
        return MockProvider(scripted=kwargs.get("scripted"))
    if provider == "anthropic":
        from traceiq.agent.providers.anthropic import AnthropicProvider

        return AnthropicProvider(**kwargs)
    if provider == "openai":
        from traceiq.agent.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(**kwargs)
    raise ValueError(f"unknown provider: {provider}")
