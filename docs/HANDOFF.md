# Handoff

## What exists

- Original TraceIQ repo (no upstream clone). Product TraceIQ; package import `traceiq`; dist name `traceiq-incident`.
- **M0:** skeleton, Makefile, CI, compose Postgres on host port **55432**, doctor CLI, clock/config/ids.
- **M1:** SQLAlchemy models, Alembic `a2434ce35bd5`, RLS + audit immutability triggers, hash-chained audit, SKIP LOCKED queue (claim committed before work), local auth (argon2 + JWT), RBAC helpers, `traceiq_app` non-superuser role for real RLS.
- Tests: `tests/unit` green (clock/ids/config + audit/queue/auth/RLS).

## Half-done

- OIDC validate helper exists; JWKS fetch and route wiring wait for M8.
- API/worker processes not started yet.

## How to run

```bash
docker compose up -d postgres
PGPASSWORD=traceiq psql -h 127.0.0.1 -p 55432 -U traceiq -d traceiq -f scripts/init_app_role.sql
TRACEIQ_MIGRATE_URL=postgresql+psycopg://traceiq:traceiq@localhost:55432/traceiq uv run alembic upgrade head
uv run pytest tests/unit -q
uv run traceiq doctor
```

## Known problems

- Host ports 5432/5433 were already taken locally; compose uses **55432**.
- Docker bootstrap user `traceiq` is a superuser (bypasses RLS). Runtime must use `traceiq_app`.

## Next 3 steps

1. M2: format parsers, Drain, Parquet writer, DuckDB queries, `ingest --dry-run`.
2. M3 analytics briefing pipeline.
3. M4 simulator + demo bundles.
