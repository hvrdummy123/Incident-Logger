"""OIDC JWT validation — JWKS supplied by caller (tests use local keys; M8 adds fetch)."""

from __future__ import annotations

from typing import Any

import jwt


def validate_oidc_token(
    token: str,
    *,
    issuer: str,
    audience: str,
    jwks: dict[str, Any],
) -> dict[str, Any]:
    """Validate RS256/ES256 token against a provided JWKS dict."""
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    keys = jwks.get("keys", [])
    matching = next((k for k in keys if k.get("kid") == kid), keys[0] if keys else None)
    if matching is None:
        raise jwt.InvalidTokenError("no JWKS key available")
    kty = matching.get("kty")
    key: Any
    if kty == "RSA":
        key = jwt.algorithms.RSAAlgorithm.from_jwk(matching)
        algorithms = ["RS256"]
    elif kty == "EC":
        key = jwt.algorithms.ECAlgorithm.from_jwk(matching)
        algorithms = ["ES256"]
    else:
        raise jwt.InvalidTokenError(f"unsupported kty: {kty}")
    return jwt.decode(
        token,
        key=key,
        algorithms=algorithms,
        audience=audience,
        issuer=issuer,
    )
