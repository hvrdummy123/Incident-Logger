# Handoff

## What exists

- Original TraceIQ repo. **M0–M7** landed (M7 core runtime; durability/resume against Postgres still M8).
- Tenancy: app scope + RLS (`traceiq_app`) + path sandbox.
- Safety: detectors/redaction with stable placeholders, egress gateway (fail-closed `NO_EXTERNAL_LLM`), injection scanner, `traceiq redact-preview`.
- Agent: state machine, read-only tools, mock provider, report schema, verifier (+ mutation tests), investigation runtime with degraded deterministic fallback.
- Simulator, demos, eval baselines.

## How to run

```bash
uv run pytest tests/ -q --ignore=tests/e2e --ignore=tests/perf --ignore=tests/chaos
uv run traceiq redact-preview samples/formats/jsonl.log
uv run traceiq eval run --suite demo --agents oracle,deterministic,latest_deploy
```

## Known problems

- Live Anthropic/OpenAI providers are seams only (raise until keys + HTTP wired).
- Investigation steps are in-memory; persist/resume via Postgres in M8.
- Cache-stampede deterministic miss still noted in ROADMAP.

## Next 3 steps

1. M8 FastAPI routes + SSE + webhook + RBAC matrix + cross-tenant API tests.
2. Persist investigation steps / queue jobs end-to-end.
3. M9 UI core (incidents, BYO wizard, investigation, report).
