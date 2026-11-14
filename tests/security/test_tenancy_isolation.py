"""Cross-tenant isolation — company A must not read or wipe company B's data."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from traceiq.db.models import Dataset, Incident, Workspace
from traceiq.ids import new_ulid
from traceiq.tenancy.context import TenantContext, clear_tenant, set_tenant
from traceiq.tenancy.paths import PathEscapeError, resolve_in_workspace, workspace_root
from traceiq.tenancy.scope import get_dataset, get_incident

pytestmark = pytest.mark.postgres

_PG_HOST = os.environ.get("TRACEIQ_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TRACEIQ_PG_PORT", "55432")
ADMIN_URL = (
    os.environ.get("TRACEIQ_ADMIN_DATABASE_URL")
    or f"postgresql+psycopg://traceiq:traceiq@{_PG_HOST}:{_PG_PORT}/traceiq"
)
APP_URL = (
    os.environ.get("TRACEIQ_APP_DATABASE_URL")
    or f"postgresql+psycopg://traceiq_app:traceiq@{_PG_HOST}:{_PG_PORT}/traceiq"
)


@pytest.fixture(scope="module")
def engines(tmp_path_factory):
    admin = create_engine(ADMIN_URL, pool_pre_ping=True)
    try:
        with admin.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres unavailable: {e}")
    with admin.begin() as conn:
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'traceiq_app') THEN
                    CREATE ROLE traceiq_app LOGIN PASSWORD 'traceiq'
                      NOSUPERUSER NOBYPASSRLS;
                  END IF;
                END$$;
                """
            )
        )
        conn.execute(text("GRANT USAGE ON SCHEMA public TO traceiq_app"))
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                "IN SCHEMA public TO traceiq_app"
            )
        )
    app = create_engine(APP_URL, pool_pre_ping=True)
    data = tmp_path_factory.mktemp("data")
    return admin, app, data


def _session(engine) -> Session:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def _set_ws(session: Session, wid: str) -> None:
    session.execute(
        text("SELECT set_config('app.workspace_id', :wid, true)"),
        {"wid": wid},
    )


def test_path_sandbox_blocks_traversal(engines) -> None:
    _, _, data_dir = engines
    wid = new_ulid()
    root = workspace_root(data_dir, wid)
    root.mkdir(parents=True)
    (root / "ok.parquet").write_text("x", encoding="utf-8")

    ok = resolve_in_workspace(data_dir, wid, "ok.parquet")
    assert ok.is_file()

    with pytest.raises(PathEscapeError):
        resolve_in_workspace(data_dir, wid, "..", "other", "secret.parquet")
    with pytest.raises(PathEscapeError):
        resolve_in_workspace(data_dir, wid, "/", "etc", "passwd")
    with pytest.raises(PathEscapeError):
        workspace_root(data_dir, "../evil")
    with pytest.raises(PathEscapeError):
        workspace_root(data_dir, "a/b")


def test_rls_blocks_cross_workspace_read_update_delete(engines) -> None:
    admin_eng, app_eng, _ = engines
    admin = _session(admin_eng)
    app = _session(app_eng)
    try:
        a, b = new_ulid(), new_ulid()
        admin.add(Workspace(id=a, name="co-a"))
        admin.add(Workspace(id=b, name="co-b"))
        admin.flush()
        incident_a = new_ulid()
        ds_a = new_ulid()
        _set_ws(admin, a)
        admin.add(
            Incident(
                id=incident_a,
                workspace_id=a,
                title="A outage",
                severity="sev1",
                status="open",
                dataset_ids=[],
            )
        )
        admin.add(
            Dataset(
                id=ds_a,
                workspace_id=a,
                content_hash="abc",
                status="ready",
                stats={},
            )
        )
        admin.commit()

        # Company B (app role + RLS): cannot see A's rows
        _set_ws(app, b)
        assert app.execute(text("SELECT id FROM incidents")).fetchall() == []
        assert app.execute(text("SELECT id FROM datasets")).fetchall() == []

        # Direct update/delete by id still blocked by RLS WITH CHECK / USING
        updated = app.execute(
            text("UPDATE incidents SET title = 'pwned' WHERE id = :id RETURNING id"),
            {"id": incident_a},
        ).fetchall()
        assert updated == []
        deleted = app.execute(
            text("DELETE FROM datasets WHERE id = :id RETURNING id"),
            {"id": ds_a},
        ).fetchall()
        assert deleted == []
        app.commit()

        # A's data still intact
        _set_ws(admin, a)
        title = admin.execute(
            text("SELECT title FROM incidents WHERE id = :id"),
            {"id": incident_a},
        ).scalar_one()
        assert title == "A outage"
        assert (
            admin.execute(
                text("SELECT count(*) FROM datasets WHERE id = :id"),
                {"id": ds_a},
            ).scalar_one()
            == 1
        )
    finally:
        app.close()
        admin.close()


def test_app_scope_hides_foreign_ids_even_if_guessed(engines) -> None:
    admin_eng, app_eng, _ = engines
    admin = _session(admin_eng)
    app = _session(app_eng)
    try:
        a, b = new_ulid(), new_ulid()
        admin.add(Workspace(id=a, name="co-a"))
        admin.add(Workspace(id=b, name="co-b"))
        admin.flush()
        iid = new_ulid()
        did = new_ulid()
        _set_ws(admin, a)
        admin.add(
            Incident(
                id=iid,
                workspace_id=a,
                title="secret",
                severity="sev2",
                status="open",
                dataset_ids=[],
            )
        )
        admin.add(Dataset(id=did, workspace_id=a, content_hash="h", status="ready", stats={}))
        admin.commit()

        _set_ws(app, b)
        set_tenant(TenantContext(workspace_id=b, user_id="u-b", role="admin"))
        try:
            assert get_incident(app, iid) is None
            assert get_dataset(app, did) is None
        finally:
            clear_tenant()
    finally:
        app.close()
        admin.close()


def test_workspace_a_cannot_delete_workspace_b_files(engines) -> None:
    _, _, data_dir = engines
    a, b = new_ulid(), new_ulid()
    b_file = resolve_in_workspace(data_dir, b, "logs.parquet")
    b_file.parent.mkdir(parents=True)
    b_file.write_text("company-b-logs", encoding="utf-8")

    # A tries to reach B via traversal — rejected before any unlink
    with pytest.raises(PathEscapeError):
        resolve_in_workspace(data_dir, a, "..", b, "logs.parquet")

    assert b_file.read_text(encoding="utf-8") == "company-b-logs"
