# Handoff

## What exists

- Original TraceIQ repo. **M0–M8** landed.
- Tenancy: app scope + RLS (`traceiq_app`) + path sandbox; API routes return 404 across tenants.
- Safety: detectors/redaction, egress gateway (`NO_EXTERNAL_LLM`), injection scanner.
- Agent: state machine, mock provider, report schema, verifier, investigation runtime.
- API: FastAPI (`traceiq serve`), local JWT auth + RBAC, incidents/investigations/reports, SSE stub, alert webhook idempotency, admin audit/egress.
- Simulator, demos, eval baselines.

## How to run

```bash
uv run pytest tests/ -q --ignore=tests/e2e --ignore=tests/perf --ignore=tests/chaos
uv run traceiq serve
uv run traceiq eval run --suite demo --agents oracle,deterministic,latest_deploy
```

## Known problems

- Live Anthropic/OpenAI providers are seams only (raise until keys + HTTP wired).
- Investigation steps still in-memory (DB tables exist; resume durability incomplete).
- Cache-stampede deterministic miss still noted in ROADMAP.
- OIDC mode not wired (local auth only).

## Next 3 steps

1. M9 UI core (incident list, BYO wizard, investigation view, report).
2. Persist investigation steps / resume against Postgres.
3. M10 ops (compose images, CI, healthchecks).
