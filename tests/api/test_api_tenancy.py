"""API tests — especially cross-tenant isolation."""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from traceiq.api.app import create_app
from traceiq.auth.local import create_user
from traceiq.auth.tokens import issue_access_token
from traceiq.db.models import ApiKey, Membership, Workspace
from traceiq.db.session import reset_engine
from traceiq.ids import new_ulid

pytestmark = pytest.mark.postgres

ADMIN_URL = "postgresql+psycopg://traceiq:traceiq@localhost:55432/traceiq"
APP_URL = "postgresql+psycopg://traceiq_app:traceiq@localhost:55432/traceiq"
SECRET = "x" * 32


@pytest.fixture(scope="module")
def engine():
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
    return create_engine(APP_URL, pool_pre_ping=True)


@pytest.fixture
def client(engine, monkeypatch):
    reset_engine()
    monkeypatch.setenv("TRACEIQ_DATABASE_URL", APP_URL)
    monkeypatch.setenv("TRACEIQ_JWT_SECRET", SECRET)
    monkeypatch.setenv("TRACEIQ_MODEL", "mock:mock-v1")
    monkeypatch.setenv("TRACEIQ_NO_EXTERNAL_LLM", "1")
    from traceiq.config import get_settings

    get_settings.cache_clear()
    reset_engine()
    app = create_app()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
    reset_engine()


def _session(engine) -> Session:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def _seed_workspace(engine, *, role: str = "investigator") -> tuple[str, str, str]:
    """Returns workspace_id, user_id, bearer token."""
    admin = create_engine(ADMIN_URL, pool_pre_ping=True)
    s = sessionmaker(bind=admin, expire_on_commit=False)()
    try:
        wid = new_ulid()
        email = f"{new_ulid()}@example.com"
        s.add(Workspace(id=wid, name=f"ws-{wid[:6]}"))
        s.flush()
        user = create_user(s, email=email, password="password-password")
        uid = user.id
        s.add(
            Membership(
                id=new_ulid(),
                workspace_id=wid,
                user_id=uid,
                role=role,
            )
        )
        s.commit()
        token = issue_access_token(user_id=uid, secret=SECRET)
        return wid, uid, token
    finally:
        s.close()
        admin.dispose()


def test_healthz(client: TestClient) -> None:
    r = client.get("/v1/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_me(client: TestClient, engine) -> None:
    wid, _uid, token = _seed_workspace(engine)
    r = client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": wid},
    )
    assert r.status_code == 200
    assert r.json()["workspace_id"] == wid
    assert r.json()["role"] == "investigator"


def test_cross_tenant_incident_isolation(client: TestClient, engine) -> None:
    wa, _ua, ta = _seed_workspace(engine, role="investigator")
    wb, _ub, tb = _seed_workspace(engine, role="investigator")

    created = client.post(
        "/v1/incidents",
        headers={"Authorization": f"Bearer {ta}", "X-Workspace-Id": wa},
        json={"title": "A secret outage", "severity": "sev1"},
    )
    assert created.status_code == 201
    incident_id = created.json()["id"]

    # B cannot list A's incident
    listed = client.get(
        "/v1/incidents",
        headers={"Authorization": f"Bearer {tb}", "X-Workspace-Id": wb},
    )
    assert listed.status_code == 200
    assert all(i["id"] != incident_id for i in listed.json())

    # B cannot fetch by id
    got = client.get(
        f"/v1/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {tb}", "X-Workspace-Id": wb},
    )
    assert got.status_code == 404
    assert got.headers["content-type"].startswith("application/problem+json")

    # A can fetch
    got_a = client.get(
        f"/v1/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {ta}", "X-Workspace-Id": wa},
    )
    assert got_a.status_code == 200
    assert got_a.json()["title"] == "A secret outage"


def test_viewer_cannot_create_incident(client: TestClient, engine) -> None:
    wid, _uid, token = _seed_workspace(engine, role="viewer")
    r = client.post(
        "/v1/incidents",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": wid},
        json={"title": "nope"},
    )
    assert r.status_code == 403


def test_investigation_and_sse(client: TestClient, engine) -> None:
    wid, _uid, token = _seed_workspace(engine, role="investigator")
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": wid}
    inc = client.post("/v1/incidents", headers=headers, json={"title": "demo"}).json()
    inv = client.post(f"/v1/incidents/{inc['id']}/investigations", headers=headers)
    assert inv.status_code == 201
    body = inv.json()
    assert body["id"]
    assert body["status"] in {"DONE", "ABSTAINED", "FAILED", "INVESTIGATING"}

    events = client.get(f"/v1/investigations/{body['id']}/events", headers=headers)
    assert events.status_code == 200
    assert "text/event-stream" in events.headers["content-type"]
    assert "event: step" in events.text


def test_webhook_creates_incident(client: TestClient, engine) -> None:
    wid, _uid, _token = _seed_workspace(engine, role="admin")
    raw_key = "test-webhook-key-123"
    admin = create_engine(ADMIN_URL)
    s = sessionmaker(bind=admin, expire_on_commit=False)()
    try:
        s.execute(
            text("SELECT set_config('app.workspace_id', :wid, true)"),
            {"wid": wid},
        )
        s.add(
            ApiKey(
                id=new_ulid(),
                workspace_id=wid,
                name="hook",
                key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
                scopes="webhook",
            )
        )
        s.commit()
    finally:
        s.close()
        admin.dispose()

    r = client.post(
        "/v1/webhooks/alerts",
        headers={
            "X-API-Key": raw_key,
            "X-Workspace-Id": wid,
            "Idempotency-Key": "once-1",
        },
        json={"title": "pager alert", "severity": "sev2"},
    )
    assert r.status_code == 201
    assert r.json()["incident_id"]

    dup = client.post(
        "/v1/webhooks/alerts",
        headers={
            "X-API-Key": raw_key,
            "X-Workspace-Id": wid,
            "Idempotency-Key": "once-1",
        },
        json={"title": "pager alert", "severity": "sev2"},
    )
    assert dup.json()["status"] == "duplicate"


def test_route_role_matrix_covers_mounted_paths() -> None:
    from traceiq.auth.rbac import ROUTE_ROLE_MATRIX

    # ensure create_app refreshed matrix
    create_app()
    required = {
        "GET /v1/incidents",
        "POST /v1/incidents",
        "GET /v1/audit",
        "POST /v1/webhooks/alerts",
    }
    assert required.issubset(set(ROUTE_ROLE_MATRIX))
