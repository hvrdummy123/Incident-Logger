"""Settings loaded from environment. Fail loud on bad config at startup."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACEIQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "dev"
    # Prefer non-superuser traceiq_app so RLS applies; migrations use TRACEIQ_MIGRATE_URL.
    database_url: str = "postgresql+psycopg://traceiq_app:traceiq@localhost:55432/traceiq"
    migrate_url: str | None = None
    data_dir: Path = Path("./data")
    jwt_secret: str = Field(default="dev-only-change-me")
    redaction_key: str = Field(default="dev-only-redaction-key")
    auth_mode: str = "local"  # local | oidc
    model: str = "mock:mock-v1"
    no_external_llm: bool = False
    model_allowlist: str = "api.anthropic.com,api.openai.com,127.0.0.1,localhost"
    default_budget_usd: float = 0.50
    max_upload_bytes: int = 2 * 1024 * 1024 * 1024
    log_level: str = "INFO"

    @field_validator("auth_mode")
    @classmethod
    def _auth_mode(cls, v: str) -> str:
        if v not in {"local", "oidc"}:
            raise ValueError("TRACEIQ_AUTH_MODE must be 'local' or 'oidc'")
        return v

    def model_allowlist_hosts(self) -> set[str]:
        return {h.strip().lower() for h in self.model_allowlist.split(",") if h.strip()}

    def parse_model(self) -> tuple[str, str]:
        """Return (provider, model_id) from TRACEIQ_MODEL=provider:model_id."""
        if ":" not in self.model:
            raise ValueError("TRACEIQ_MODEL must look like provider:model_id")
        provider, model_id = self.model.split(":", 1)
        provider = provider.strip().lower()
        if provider not in {"anthropic", "openai", "mock"}:
            raise ValueError(f"unknown model provider: {provider}")
        return provider, model_id


@lru_cache
def get_settings() -> Settings:
    return Settings()
