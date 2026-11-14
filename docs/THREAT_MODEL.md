# Threat model (living doc)

Focus: **tenant isolation**. A user in company A must not read, modify, or delete company B’s incidents, datasets, or on-disk logs.

## How TraceIQ enforces isolation (three layers)

1. **Application scope** (`tenancy/scope.py`, `tenancy/context.py`)  
   Every lookup includes `workspace_id` from the authenticated tenant context. Guessing another tenant’s ULID returns `None` / 404 — never the row.

2. **Postgres RLS** (`db/rls.py`) with a **non-superuser** role (`traceiq_app`)  
   `FORCE ROW LEVEL SECURITY` + policy `workspace_id = current_setting('app.workspace_id')`.  
   Even a buggy query without a WHERE clause cannot see or mutate another tenant’s rows.  
   The compose bootstrap user `traceiq` is a superuser (Docker default) and **must not** be used at runtime — migrations only. See `scripts/init_app_role.sql`.

3. **Filesystem sandbox** (`tenancy/paths.py`)  
   Datasets live only under `data/<workspace_id>/…`. Path resolution rejects `..`, absolute paths, and workspace ids containing slashes. Cross-tenant delete via path traversal fails closed with `PathEscapeError` before any unlink.

## STRIDE snapshot (tenant boundary)

| Asset | Spoofing | Tampering | Repudiation | Info disclosure | DoS | Elevation |
|---|---|---|---|---|---|---|
| API IDs | JWT/API key required (M8) | RLS blocks UPDATE/DELETE across tenants | Audit hash chain | RLS + app filter | upload limits (M2+) | RBAC roles |
| Dataset files | workspace in path | sandbox resolve | audit on delete | sandbox | size/ratio limits | no shared dirs |
| Model egress | allow-list hosts | N/A | egress ledger | redaction before send (M6) | budget caps | NO_EXTERNAL_LLM |

## Tests that prove it

- `tests/security/test_tenancy_isolation.py` — RLS read/update/delete denied across workspaces; path traversal blocked; app scope returns None for foreign IDs.
- `tests/unit/test_audit_queue_auth.py` — RLS hide other workspace incidents.

## Model egress (M6)

- All provider calls go through `safety/egress.py` only.
- Content is redacted before send; gateway asserts originals are absent from the payload.
- `TRACEIQ_NO_EXTERNAL_LLM=1` blocks non-mock providers and records a ledger row (`blocked`).
- Prompt-injection-shaped log lines are flagged into the report (`injection_suspected`), never executed.

## What we still must not mess up (M8+)

- Never connect the API/worker as a DB superuser.
- Every route that takes an id must use scoped getters (matrix test will fail open routes).
- Dataset delete must resolve through `resolve_in_workspace` then remove only that tree.
- Do not import provider SDKs from outside `agent/providers/` or call them outside the egress gateway.
