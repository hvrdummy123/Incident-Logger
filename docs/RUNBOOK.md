# TraceIQ runbook

## SLOs (targets — measure in M11)

| Signal | Target |
| --- | --- |
| Investigation success rate (mock) | ≥ 99% non-crash |
| API p95 latency (health/list) | TODO(real-run) |
| Queue age | < 60s under demo load |

## Compose stack

```bash
cp .env.example .env
docker compose up -d --build
# UI http://localhost:8080  API http://localhost:8000/v1/healthz
```

Postgres is on host port **55432**. App role `traceiq_app` is created via `scripts/init_app_role.sql` on first volume init; for existing volumes run that script once as the bootstrap user.

## If this breaks

| Symptom | Check |
| --- | --- |
| Postgres down | `docker compose ps`; `pg_isready -h 127.0.0.1 -p 55432 -U traceiq` |
| API 500 on login | JWT secret set? Migrations applied? `docker compose logs api` |
| Worker idle forever | Jobs table empty is normal until enqueue; `docker compose logs worker` |
| Cross-tenant leak suspected | Re-run `pytest tests/security tests/api -q`; confirm app role has `NOBYPASSRLS` |
| Model timeout | `TRACEIQ_NO_EXTERNAL_LLM=1` or raise budget; check egress ledger |
| Bad upload | BYO preview rejects null bytes; CLI `traceiq ingest --dry-run` |

## Alerts (when metrics are scraped)

- `traceiq_jobs_failed_total` rising
- `traceiq_egress_blocked_total` unexpected spikes
- Investigation duration histogram p95 above runbook target

## Graceful shutdown

API/worker handle SIGTERM. Worker finishes or releases the current lease on the next loop; do not `kill -9` unless the process is wedged.
