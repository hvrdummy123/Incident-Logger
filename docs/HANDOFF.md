# Handoff

## What exists

- Original TraceIQ repo. **M0–M11** landed (M12 stretch optional).
- See `REPORT.md` for measured test/eval numbers (2026-11-14).
- Compose: `docker compose up -d --build` → UI :8080, API :8000, Postgres host :55432.

## How to run

```bash
docker compose up -d --build
uv run pytest tests/ -q --ignore=tests/e2e --ignore=tests/perf --ignore=tests/chaos
cd web && npm test && npm run build
uv run traceiq eval run --suite demo --agents oracle,deterministic,latest_deploy
```

## Known problems

- Held-out `test` eval split is empty (n=0).
- Live LLM providers not wired; no API keys used.
- Investigation durability / worker handlers / Playwright still thin.
- Deterministic miss on cache stampede.

## Next 3 steps

1. Seed a local user for compose UI login; walk `docs/HUMAN_TEST.md`.
2. Freeze held-out scenarios; run test split once; update `docs/EVAL.md`.
3. Optional M12: Playwright smoke, Grafana JSON, live provider HTTP.
