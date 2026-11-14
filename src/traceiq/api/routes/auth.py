"""Local auth routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from traceiq.api.deps import AuthUser, db_session, require_user, settings_dep
from traceiq.api.errors import AppError
from traceiq.auth.local import login
from traceiq.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login")
def login_route(
    body: LoginBody,
    session: Session = Depends(db_session),
    settings: Settings = Depends(settings_dep),
) -> dict[str, str]:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from traceiq.db.models import Membership, User

    tokens = login(session, body.email, body.password, jwt_secret=settings.jwt_secret)
    if tokens is None:
        raise AppError(401, "Unauthorized", "Invalid email or password")
    user = session.scalar(select(User).where(User.email == body.email))
    workspace_id = ""
    if user is not None:
        # Memberships are RLS-scoped; resolve via migrate role (no workspace yet).
        admin_url = settings.migrate_url or settings.database_url
        engine = create_engine(admin_url, pool_pre_ping=True)
        admin = sessionmaker(bind=engine, expire_on_commit=False)()
        try:
            memberships = admin.scalars(
                select(Membership).where(Membership.user_id == user.id)
            ).all()
            if len(memberships) == 1:
                workspace_id = memberships[0].workspace_id
        finally:
            admin.close()
            engine.dispose()
    return {**tokens, "workspace_id": workspace_id}


@router.get("/me")
def me(user: AuthUser = Depends(require_user)) -> dict[str, str]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "workspace_id": user.workspace_id,
        "role": user.role,
    }
