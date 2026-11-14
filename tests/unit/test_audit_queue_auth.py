from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from traceiq.audit.chain import append_audit, verify_chain
from traceiq.auth.local import create_user, hash_password, login, verify_password
from traceiq.auth.rbac import Role, has_at_least
from traceiq.db.models import Incident, Workspace
from traceiq.ids import new_ulid
from traceiq.queue.jobs import claim_one, complete, enqueue
from traceiq.queue.worker import run_once

pytestmark = pytest.mark.postgres

# Superuser for setup / trigger tests; app role for RLS assertions.
ADMIN_URL = "postgresql+psycopg://traceiq:traceiq@localhost:55432/traceiq"
APP_URL = "postgresql+psycopg://traceiq_app:traceiq@localhost:55432/traceiq"


@pytest.fixture(scope="module")
def admin_engine():
    eng = create_engine(ADMIN_URL, pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres unavailable: {e}")
    return eng


@pytest.fixture(scope="module")
def app_engine(admin_engine):
    # Ensure app role exists (idempotent).
    with admin_engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'traceiq_app') THEN
                    CREATE ROLE traceiq_app LOGIN PASSWORD 'traceiq' NOSUPERUSER NOBYPASSRLS;
                  END IF;
                END$$;
                """
            )
        )
        conn.execute(text("GRANT USAGE ON SCHEMA public TO traceiq_app"))
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO traceiq_app"
            )
        )
    try:
        eng = create_engine(APP_URL, pool_pre_ping=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"traceiq_app role unavailable: {e}")


@pytest.fixture
def admin_session(admin_engine):
    factory = sessionmaker(bind=admin_engine, autoflush=False, expire_on_commit=False)
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


@pytest.fixture
def app_session(app_engine):
    factory = sessionmaker(bind=app_engine, autoflush=False, expire_on_commit=False)
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _set_ws(session: Session, workspace_id: str) -> None:
    session.execute(
        text("SELECT set_config('app.workspace_id', :wid, true)"),
        {"wid": workspace_id},
    )


def test_password_hash_roundtrip() -> None:
    h = hash_password("s3cret-pass")
    assert verify_password(h, "s3cret-pass")
    assert not verify_password(h, "wrong")


def test_rbac_ordering() -> None:
    assert has_at_least("admin", Role.VIEWER)
    assert has_at_least("investigator", Role.INVESTIGATOR)
    assert not has_at_least("viewer", Role.ADMIN)


def test_audit_chain_verify_and_immutability(admin_session: Session) -> None:
    wid = new_ulid()
    admin_session.add(Workspace(id=wid, name="audit-ws"))
    admin_session.flush()
    _set_ws(admin_session, wid)

    append_audit(admin_session, workspace_id=wid, actor="u1", action="login")
    append_audit(admin_session, workspace_id=wid, actor="u1", action="upload", target="ds1")
    admin_session.commit()
    _set_ws(admin_session, wid)

    result = verify_chain(admin_session, wid)
    assert result.ok
    assert result.checked == 2

    with pytest.raises(Exception, match="append-only"):
        admin_session.execute(
            text("UPDATE audit_log SET action = 'tampered' WHERE workspace_id = :wid AND seq = 1"),
            {"wid": wid},
        )
        admin_session.flush()
    admin_session.rollback()
    _set_ws(admin_session, wid)

    admin_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update"))
    admin_session.execute(
        text("UPDATE audit_log SET hash = '00' WHERE workspace_id = :wid AND seq = 2"),
        {"wid": wid},
    )
    admin_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update"))
    admin_session.commit()
    _set_ws(admin_session, wid)

    broken = verify_chain(admin_session, wid)
    assert not broken.ok
    assert broken.first_break_seq == 2
    assert broken.reason == "hash mismatch"


def test_queue_claim_complete_and_dead_letter(admin_session: Session) -> None:
    admin_session.execute(text("DELETE FROM jobs"))
    admin_session.commit()

    kind_ok = f"noop-{new_ulid()}"
    job_id = enqueue(admin_session, kind=kind_ok, payload={"n": 1})
    admin_session.commit()

    claimed = claim_one(admin_session, worker_id="w1")
    assert claimed is not None
    assert claimed.id == job_id
    complete(admin_session, claimed.id)
    admin_session.commit()

    assert claim_one(admin_session, worker_id="w1") is None

    kind_bad = f"explode-{new_ulid()}"
    bad = enqueue(admin_session, kind=kind_bad, payload={})
    admin_session.commit()

    def boom(_s: Session, _j: object) -> None:
        raise RuntimeError("boom")

    for _ in range(5):
        # backoff_base_seconds=0 so retries are immediately claimable in this test
        run_once(
            admin_session,
            worker_id="w2",
            handlers={kind_bad: boom},
            backoff_base_seconds=0.0,
        )

    row = (
        admin_session.execute(
            text("SELECT status, attempts FROM jobs WHERE id = :id"),
            {"id": bad},
        )
        .mappings()
        .one()
    )
    assert row["status"] == "dead"
    assert row["attempts"] >= 5


def test_local_login(admin_session: Session) -> None:
    wid = new_ulid()
    admin_session.add(Workspace(id=wid, name="auth-ws"))
    admin_session.flush()
    email = f"oncall-{new_ulid()[:8]}@example.com"
    user = create_user(admin_session, email=email, password="correct-horse")
    tokens = login(admin_session, email, "correct-horse", jwt_secret="x" * 32)
    assert tokens is not None
    assert "access_token" in tokens
    assert login(admin_session, email, "nope", jwt_secret="x" * 32) is None
    assert user.email == email.lower()


def test_rls_hides_other_workspace_incidents(app_session: Session, admin_session: Session) -> None:
    a, b = new_ulid(), new_ulid()
    admin_session.add(Workspace(id=a, name="A"))
    admin_session.add(Workspace(id=b, name="B"))
    admin_session.commit()

    _set_ws(app_session, a)
    app_session.add(
        Incident(id=new_ulid(), workspace_id=a, title="A only", severity="sev2", status="open")
    )
    app_session.commit()

    _set_ws(app_session, b)
    rows = app_session.execute(text("SELECT id FROM incidents")).fetchall()
    assert rows == []

    _set_ws(app_session, a)
    rows = app_session.execute(text("SELECT title FROM incidents")).fetchall()
    assert [r[0] for r in rows] == ["A only"]
