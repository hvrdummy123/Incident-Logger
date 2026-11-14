"""Local username/password auth with argon2id hashes."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from traceiq.auth.tokens import issue_access_token
from traceiq.db.models import RefreshToken, User
from traceiq.ids import new_ulid

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_user(
    session: Session,
    *,
    email: str,
    password: str,
    display_name: str = "",
) -> User:
    user = User(
        id=new_ulid(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        display_name=display_name or email.split("@")[0],
    )
    session.add(user)
    session.flush()
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    email_norm = email.lower().strip()
    user = session.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if user is None or not user.password_hash:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


def issue_refresh_token(session: Session, user_id: str, *, days: int = 14) -> str:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    row = RefreshToken(
        id=new_ulid(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=days),
    )
    session.add(row)
    session.flush()
    return raw


def login(session: Session, email: str, password: str, *, jwt_secret: str) -> dict[str, str] | None:
    user = authenticate(session, email, password)
    if user is None:
        return None
    access = issue_access_token(user_id=user.id, secret=jwt_secret)
    refresh = issue_refresh_token(session, user.id)
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}
