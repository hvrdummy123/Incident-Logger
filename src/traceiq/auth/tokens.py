"""JWT access tokens (local mode)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt


def issue_access_token(
    *,
    user_id: str,
    secret: str,
    minutes: int = 15,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])
