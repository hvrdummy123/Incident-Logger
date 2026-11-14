"""ID helpers — ULIDs for evidence and investigation steps."""

from __future__ import annotations

import ulid


def new_ulid() -> str:
    return str(ulid.new())


def evidence_id() -> str:
    return f"ev_{new_ulid()}"
