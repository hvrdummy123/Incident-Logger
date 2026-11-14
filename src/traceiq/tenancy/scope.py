"""Application-layer workspace scoping — pairs with Postgres RLS."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from traceiq.db.models import Dataset, Incident
from traceiq.tenancy.context import get_tenant


def require_workspace_id() -> str:
    return get_tenant().workspace_id


def get_incident(session: Session, incident_id: str) -> Incident | None:
    """Fetch by id only if it belongs to the current workspace (app filter + RLS)."""
    wid = require_workspace_id()
    return session.scalar(
        select(Incident).where(Incident.id == incident_id, Incident.workspace_id == wid)
    )


def get_dataset(session: Session, dataset_id: str) -> Dataset | None:
    wid = require_workspace_id()
    return session.scalar(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.workspace_id == wid)
    )
