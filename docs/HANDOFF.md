# Handoff

## What exists

- Original TraceIQ repo. **M0–M9** landed (M9 = core UI cut line).
- Tenancy: app scope + RLS (`traceiq_app`) + path sandbox; API cross-tenant 404s.
- Safety: redaction, egress gateway (`NO_EXTERNAL_LLM`), injection scanner.
- Agent: state machine, mock provider, verifier, investigation runtime.
- API: FastAPI (`traceiq serve`), JWT + RBAC, datasets preview for BYO, SSE steps, webhooks.
- Web: Vite/React/TS — login, incidents (`j/k`/`/`), BYO wizard, investigation panes, report + feedback.
- Simulator, demos, eval baselines.

## How to run

```bash
uv run pytest tests/ -q --ignore=tests/e2e --ignore=tests/perf --ignore=tests/chaos
cd web && npm test && npx tsc --noEmit
uv run traceiq serve
cd web && npm run dev
```

## Known problems

- Live Anthropic/OpenAI providers are seams only.
- Investigation step durability/resume incomplete; SSE uses in-memory cache.
- BYO creates the incident after preview; parquet materialization still CLI-oriented.
- Evals/admin UI pages cut for now (per cut line).
- OIDC not wired (local auth only).
- Playwright/axe e2e not yet in CI for the UI.

## Next 3 steps

1. M10 ops — Docker images for api/worker/web, compose wiring, CI.
2. Persist investigation steps / resume against Postgres.
3. M11 docs/REPORT + held-out eval numbers from real runs.
