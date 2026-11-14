"""Row-level security policies — defense in depth on top of app scoping."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Tenant-owned tables that must carry workspace_id RLS.
TENANT_TABLES = (
    "memberships",
    "api_keys",
    "datasets",
    "incidents",
    "investigations",
    "evidence",
    "reports",
    "audit_log",
    "model_calls",
)


def apply_rls(conn: Connection) -> None:
    """Enable RLS + policies. Idempotent enough for migrations."""
    for table in TENANT_TABLES:
        conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        # Drop/recreate so re-running migrations is safe.
        conn.execute(text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        conn.execute(
            text(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                USING (workspace_id = current_setting('app.workspace_id', true))
                WITH CHECK (workspace_id = current_setting('app.workspace_id', true))
                """
            )
        )


def install_audit_immutability_triggers(conn: Connection) -> None:
    conn.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION audit_log_forbid_mutate() RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'audit_log is append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    conn.execute(text("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log"))
    conn.execute(text("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log"))
    conn.execute(
        text(
            """
            CREATE TRIGGER audit_log_no_update
            BEFORE UPDATE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_forbid_mutate();
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TRIGGER audit_log_no_delete
            BEFORE DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_forbid_mutate();
            """
        )
    )
