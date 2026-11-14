"""Role checks — viewer < investigator < admin."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    VIEWER = "viewer"
    INVESTIGATOR = "investigator"
    ADMIN = "admin"


_RANK = {Role.VIEWER: 1, Role.INVESTIGATOR: 2, Role.ADMIN: 3}


def has_at_least(role: str, required: Role) -> bool:
    try:
        return _RANK[Role(role)] >= _RANK[required]
    except ValueError:
        return False


# Route → minimum role. Expanded in M8 as routes land; matrix test will use this table.
ROUTE_ROLE_MATRIX: dict[str, Role] = {
    "GET /v1/healthz": Role.VIEWER,  # public in practice; matrix placeholder
    "GET /v1/me": Role.VIEWER,
    "GET /v1/incidents": Role.VIEWER,
    "POST /v1/incidents": Role.INVESTIGATOR,
    "POST /v1/incidents/{id}/investigations": Role.INVESTIGATOR,
    "POST /v1/reports/{id}/feedback": Role.INVESTIGATOR,
    "GET /v1/audit": Role.ADMIN,
    "GET /v1/egress-ledger": Role.ADMIN,
}
