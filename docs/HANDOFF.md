# Handoff

## What exists

- Original TraceIQ repo. **M0–M10** landed.
- Tenancy: app scope + RLS (`traceiq_app`) + path sandbox; API cross-tenant 404s.
- Safety: redaction, egress gateway (`NO_EXTERNAL_LLM`), injection scanner.
- Agent: state machine, mock provider, verifier, investigation runtime.
- API + worker + web compose stack; `docs/RUNBOOK.md`.
- Web: Vite/React — incidents, BYO wizard, investigation, report.

## How to run

```bash
docker compose up -d --build
# UI http://localhost:8080  API :8000  Postgres host :55432

uv run pytest tests/ -q --ignore=tests/e2e --ignore=tests/perf --ignore=tests/chaos
cd web && npm test && npm run build
```

## Known problems

- Live Anthropic/OpenAI providers are seams only.
- Investigation step durability/resume incomplete; SSE uses in-memory cache.
- Worker handlers are empty stubs (unknown kinds dead-letter).
- Playwright/axe e2e and Grafana dashboard JSON still TODO.
- OIDC not wired.

## Next 3 steps

1. M11 docs — ARCHITECTURE diagrams, REPORT.md with measured numbers.
2. Persist investigation steps / resume against Postgres.
3. Wire real worker job handlers + optional Playwright smoke.
