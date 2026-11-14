"""Shared pytest fixtures."""

from __future__ import annotations

# Ensure TRACEIQ_* defaults never pick up a developer's real secrets in unit tests.
import os

os.environ.setdefault("TRACEIQ_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("TRACEIQ_REDACTION_KEY", "test-redaction-key")
os.environ.setdefault("TRACEIQ_MODEL", "mock:mock-v1")
os.environ.setdefault("TRACEIQ_NO_EXTERNAL_LLM", "1")
