# TraceIQ REPORT

Factual status after M0–M10 (+ M11 docs). Numbers below come from commands run on **2026-11-14** on this machine unless marked `TODO(real-run)`.

## What was built

- **Product:** TraceIQ (dist `traceiq-incident`, import/CLI `traceiq`).
- **Layout:** modular monolith — `api` / `worker` / `web` + Postgres (`traceiq_app` RLS).
- **Python packages:** config, db, auth, tenancy, ingest, store, analytics, sim, evals, safety, agent, api, queue (~95 `.py` modules under `src/traceiq`, ~6781 lines).
- **Web:** Vite/React/TS (~26 source files, ~1944 lines TS/TSX) — login, incidents, BYO wizard, investigation, report.
- **API surface (mounted):** health, auth/login, me, incidents CRUD-ish, datasets/preview, investigations (+ SSE), reports + feedback, admin audit/egress, webhooks/alerts.
- **Demos:** three bundles (bad deploy, DB pool, cache stampede).
- **Compose:** postgres :55432, migrate, api :8000, worker, web :8080.

## Test results

| Suite | Result |
| --- | --- |
| `pytest tests/ --ignore=e2e,perf,chaos` | **56 passed**, 0 failed, 0 skipped (1 Starlette deprecation warning) |
| Vitest (`cd web && npm test`) | **6 passed** |
| `tsc --noEmit` / `npm run build` | pass (JS gzip ~76 KB for main bundle) |
| ruff + mypy strict on `src/traceiq` | pass |
| Docker `traceiq-api:local` / `traceiq-web:local` | build succeeded |
| e2e / perf / chaos dirs | empty — not run |
| Playwright + axe | **not implemented** (cut / deferred) |
| Live LLM agent sweep | **skipped** — no `ANTHROPIC_API_KEY` / OpenAI key in env |

Coverage on named modules (one run with `--cov` on analytics/ingest/safety/verify/runtime):

| Area | Cover |
| --- | --- |
| Combined named modules | **87%** statements (1125 stmts, 150 miss) |
| `agent/runtime.py` | 79% |
| `agent/verify.py` | 82% |
| `analytics/*` (measured files) | 94–98% |
| `ingest/*` (measured) | 60–97% (normalize/detect lower) |
| `safety/*` (measured) | 75–94% |

Target was ≥85% on those areas as a group — **met at 87%**. Individual files below 85%: `runtime.py`, `verify.py`, `detect.py`, `normalize.py`, `detectors.py`, `egress.py`.

## Evaluation results

Command:

```bash
uv run traceiq eval run --suite demo --agents oracle,deterministic,latest_deploy
```

| Agent | service_top1 | category_ok | trigger_ok | n |
| --- | --- | --- | --- | --- |
| oracle | **1.00** | 1.00 | 1.00 | 3 |
| deterministic | **0.67** | 1.00 | 0.33 | 3 |
| latest_deploy | **0.33** | 1.00 | 0.33 | 3 |

Failure gallery (demo):

- `cache_stampede_demo`: deterministic + latest_deploy both top-1 **cart** (true: **redis-cache**).
- `db_pool_demo`: latest_deploy top-1 **cart** (true: **payments**); deterministic correct.

Dev split (`--suite dev`, n=2):

| Agent | service_top1 | notes |
| --- | --- | --- |
| oracle | 0.50 | abstains correctly on `unsolvable_dev_101` |
| deterministic | 0.50 | does not abstain on unsolvable |
| latest_deploy | 0.00 | fooled on `db_pool_dev_100` |

**Held-out test split:** ran once via `uv run traceiq eval run --suite test …` → **n_scenarios=0** (no scenarios tagged `split=test` yet). No accuracy/CI to report. Regenerating a frozen held-out set is an open next step.

**Real model:** not run. Command when keys exist:

```bash
TRACEIQ_MODEL=anthropic:claude-… TRACEIQ_NO_EXTERNAL_LLM=0 \
  uv run traceiq eval run --suite demo --agents agent --max-cost-usd 3
```

(Exact agent CLI flags: TODO if not wired — use API investigation with live provider once HTTP adapters land.)

## Performance vs NFRs

| NFR | Result |
| --- | --- |
| Demo eval wall time | ~2.4s for 3 scenarios (this host) |
| Full pytest (ignored e2e/perf/chaos) | ~5.4s |
| Initial web JS gzip | ~76 KB (under 300 KB budget) |
| Ingest/query NFRs at scale | **TODO(real-run)** — no bench numbers recorded this session |

## What was cut (and why)

Per prompt cut line, deferred or thin:

- M12 stretch (extra connectors, Slack, etc.)
- kustomize / Grafana dashboard JSON polish (dirs empty)
- Evals page charts + admin UI pages
- OIDC (local JWT only)
- Playwright e2e + axe-core gate
- Full 16 fault-type simulator matrix → fewer demo/dev scenarios
- Live provider HTTP clients (seams raise until keys + wiring)
- Investigation durability/resume against Postgres (tables exist; API still sync mock + in-memory SSE cache)
- Worker job handlers (loop runs; kinds not dispatched yet)

**Not cut:** ground-truth discipline on demos, verifier + mutation tests, redaction/egress, tenancy/RLS tests, BYO dry-run preview, eval harness.

## Bugs found during the build (raw material)

- PyPI name `traceiq` taken → dist `traceiq-incident`.
- Host Postgres ports busy → compose **55432**.
- Superuser bypassed RLS → dedicated `traceiq_app` `NOBYPASSRLS`.
- Queue claim rolled back on handler failure → commit lease before work.
- Audit tamper test wiped rows via rollback → commit before mutate.
- DuckDB `fetchdf` needed numpy → use `fetchall`.
- API test emails truncated ULID → collisions; use full ULID emails.
- UI needed `X-Workspace-Id`; login now returns single membership workspace id.
- Dataset preview binary check vs JSON body encoding — reject embedded nulls before ingest.

## Open risks

- Cross-tenant safety depends on always using `traceiq_app` in runtime (compose does; misconfigured `TRACEIQ_DATABASE_URL` as superuser would weaken RLS).
- SSE step stream is process-local until workers own it.
- Deterministic miss on cache stampede remains.
- Empty held-out split means no frozen test score yet.
- npm audit reported vulnerabilities in the web toolchain (see `npm audit`); not triaged into `SECURITY.md` this session.

## Next steps for a human

1. `docker compose up -d --build` → open http://localhost:8080 → create a user (CLI/seed) → load demo → run investigation → check citations.
2. Fill `docs/HUMAN_NOTES.md`; run `docs/HUMAN_TEST.md` checklist.
3. Record a short GIF of BYO wizard + report.
4. Add held-out `split=test` scenarios, freeze, run **once**, paste into `docs/EVAL.md`.
5. With a real API key, run a small mock→live comparison and budget-capped sweep.
6. Try BYO on a real (redacted) log sample; file gaps in parse formats.
