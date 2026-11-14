"""FastAPI dependencies — auth, tenancy, RBAC, DB session."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from traceiq.api.errors import AppError
from traceiq.auth.rbac import Role, has_at_least
from traceiq.auth.tokens import decode_access_token
from traceiq.config import Settings, get_settings
from traceiq.db.models import Membership, User
from traceiq.db.session import get_session_factory
from traceiq.tenancy.context import TenantContext, clear_tenant, set_tenant

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    user_id: str
    email: str
    workspace_id: str
    role: str


def settings_dep() -> Settings:
    return get_settings()


def db_session() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        clear_tenant()
        session.close()


def _current_user(
    creds: HTTPAuthorizationCredentials | None,
    workspace_id: str | None,
    session: Session,
    settings: Settings,
) -> AuthUser:
    if creds is None or not creds.credentials:
        raise AppError(401, "Unauthorized", "Missing bearer token")
    if not workspace_id:
        raise AppError(400, "Bad Request", "X-Workspace-Id header required")
    try:
        payload = decode_access_token(creds.credentials, secret=settings.jwt_secret)
    except Exception as e:  # noqa: BLE001
        raise AppError(401, "Unauthorized", f"Invalid token: {e}") from e
    user_id = str(payload.get("sub", ""))
    user = session.get(User, user_id)
    if user is None:
        raise AppError(401, "Unauthorized", "User not found")

    # RLS + membership
    session.execute(
        text("SELECT set_config('app.workspace_id', :wid, true)"),
        {"wid": workspace_id},
    )
    membership = session.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user_id,
        )
    )
    if membership is None:
        # Do not leak whether the workspace exists
        raise AppError(404, "Not Found", "Workspace not found")

    set_tenant(
        TenantContext(workspace_id=workspace_id, user_id=user_id, role=membership.role)
    )
    return AuthUser(
        user_id=user_id,
        email=user.email,
        workspace_id=workspace_id,
        role=membership.role,
    )


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    session: Session = Depends(db_session),
    settings: Settings = Depends(settings_dep),
) -> AuthUser:
    return _current_user(creds, x_workspace_id, session, settings)


def require_role(min_role: Role) -> Any:
    def _inner(user: AuthUser = Depends(require_user)) -> AuthUser:
        if not has_at_least(user.role, min_role):
            raise AppError(403, "Forbidden", f"Requires role {min_role.value} or higher")
        return user

    return _inner


def request_id(request: Request) -> str:
    return request.headers.get("X-Request-Id", "")
