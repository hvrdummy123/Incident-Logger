"""Engine + session factory."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from traceiq.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(url: str | None = None) -> Engine:
    global _engine, _SessionLocal
    if _engine is None or url is not None:
        settings = get_settings()
        _engine = create_engine(url or settings.database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(
            bind=_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope(workspace_id: str | None = None) -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        if workspace_id is not None:
            # RLS backstop — must be SET LOCAL inside a transaction.
            session.execute(
                text("SELECT set_config('app.workspace_id', :wid, true)"),
                {"wid": workspace_id},
            )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Test helper — drop the cached engine so a new URL can be used."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
