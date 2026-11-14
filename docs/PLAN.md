# TraceIQ build plan

Working from `incident_agent_prompt.md`. Product name is **TraceIQ** (not Sherlog). This is an original codebase — empty repo, no clone of any existing Sherlog/TraceIQ project.

## Milestones

- [x] **M0 Preflight** — toolchain check, skeleton, CI stub, Makefile, name decision
- [x] **M1 Platform base** — config, clock, DB models, Alembic, RLS, auth/RBAC, audit, queue, doctor
- [ ] **M2 Ingest and store** — parsers, Drain, Parquet, DuckDB, dry-run
- [ ] **M3 Analytics** — anomalies, suspects, timeline, compare_windows
- [ ] **M4 Simulator and demos** — world, faults, three demo bundles
- [ ] **M5 Baselines and eval harness** — gate: oracle 100%, decoys defeat heuristics
- [ ] **M6 Safety** — redaction, egress, injection, NO_EXTERNAL_LLM
- [ ] **M7 Agent runtime** — state machine, tools, verifier, resume/replay
- [ ] **M8 API** — REST, SSE, webhooks, OpenAPI
- [ ] **M9 UI** — incidents, BYO wizard, investigation, report (core cut line)
- [ ] **M10 Ops** — compose, observability, CI, perf/chaos
- [ ] **M11 Docs and final verification** — REPORT.md, held-out eval once
- [ ] **M12 Stretch** — only if M0–M11 green

## Cut line (if needed)

Keep M0–M8 + core M9 + eval harness. Cut order: M12 → kustomize/Grafana polish → evals charts → OIDC → extra demo decoys → fault catalog 16→10. Never cut: verifier, redaction/egress, tenancy, durability, held-out discipline, BYO dry-run.

## Current

Next up: **M2**.
