# Handoff

## What exists

- Original TraceIQ repo. **M0–M5** landed.
- Tenancy: app scope + RLS (`traceiq_app`) + path sandbox. See `docs/THREAT_MODEL.md`.
- Ingest + analytics briefing.
- Simulator (deterministic), three demo bundles under `demo/`, answer keys under `demo/answers/`.
- Eval harness: `traceiq eval run --suite demo|dev|train` with oracle / deterministic / most_errors / latest_deploy.
- Gate check (demo split): oracle top-1 = 1.0; latest_deploy < 1.0 (decoys work); deterministic > latest_deploy.

## How to run

```bash
docker compose up -d postgres
./scripts/make_demo.sh
uv run pytest tests/ -q --ignore=tests/e2e --ignore=tests/perf --ignore=tests/chaos
uv run traceiq eval run --suite demo --agents oracle,deterministic,latest_deploy,most_errors
uv run traceiq demo list
uv run traceiq ingest samples/formats/jsonl.log --dry-run
```

## Known problems

- Runtime DB must use `traceiq_app` (not superuser).
- Postgres on host port **55432**.
- Deterministic still misses cache-stampede sometimes (ranks decoy `cart`) — noted for weight tuning on train only in a later pass.
- Demo bundles are generated artifacts; regenerate with `./scripts/make_demo.sh`.

## Next 3 steps

1. M6 safety: redaction, egress gateway, injection detector, NO_EXTERNAL_LLM.
2. M7 agent runtime + verifier.
3. M8 API with cross-tenant route security tests.
