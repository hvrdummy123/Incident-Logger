"""Workspace scoping context for the request / job lifetime."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    workspace_id: str
    user_id: str | None
    role: str


_current: ContextVar[TenantContext | None] = ContextVar("traceiq_tenant", default=None)


def set_tenant(ctx: TenantContext) -> None:
    _current.set(ctx)


def clear_tenant() -> None:
    _current.set(None)


def get_tenant() -> TenantContext:
    ctx = _current.get()
    if ctx is None:
        raise RuntimeError("no tenant context set")
    return ctx


def try_get_tenant() -> TenantContext | None:
    return _current.get()
