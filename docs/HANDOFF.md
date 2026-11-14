# Handoff

## What exists

- Original TraceIQ repo. M0–M3 landed.
- **Tenancy (security):** app-scoped getters, Postgres RLS via `traceiq_app`, filesystem sandbox under `data/<workspace_id>/`. See `docs/THREAT_MODEL.md`. Tests in `tests/security/test_tenancy_isolation.py`.
- **Ingest:** jsonl/logfmt/nginx/cri/syslog/plain + stack grouping, format detect, Drain, parse report, Parquet writer, DuckDB query, `traceiq ingest --dry-run`.
- **Analytics:** robust-z/CUSUM, new templates, change correlation, service graph, suspect ranking with contributions, compare_windows, timeline, `build_briefing()`.

## How to run

```bash
docker compose up -d postgres
PGPASSWORD=traceiq psql -h 127.0.0.1 -p 55432 -U traceiq -d traceiq -f scripts/init_app_role.sql
TRACEIQ_MIGRATE_URL=postgresql+psycopg://traceiq:traceiq@localhost:55432/traceiq uv run alembic upgrade head
uv run pytest tests/unit tests/ingest tests/security -q
uv run traceiq ingest samples/formats/jsonl.log --dry-run
uv run traceiq doctor
```

## Known problems

- Runtime DB URL must use `traceiq_app` (not superuser `traceiq`) or RLS is bypassed.
- Host Postgres port is **55432**.

## Next 3 steps

1. M4 simulator + demo bundles.
2. M5 eval harness / baselines.
3. M6/M8 keep hammering cross-tenant API tests as routes appear.
