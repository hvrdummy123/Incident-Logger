# TraceIQ build plan

Working from `incident_agent_prompt.md`. Product name is **TraceIQ**. Original codebase — no clone.

## Milestones

- [x] **M0 Preflight**
- [x] **M1 Platform base**
- [x] **M2 Ingest and store** (+ tenancy security tests)
- [x] **M3 Analytics**
- [x] **M4 Simulator and demos**
- [x] **M5 Baselines and eval harness**
- [x] **M6 Safety** — redaction, egress, injection, NO_EXTERNAL_LLM
- [x] **M7 Agent runtime** — state machine, tools, mock provider, verifier (core)
- [x] **M8 API** — REST + SSE + webhook + RBAC + cross-tenant 404s
- [x] **M9 UI** — incident list, BYO wizard, investigation, report (+ Vitest)
- [ ] **M10 Ops**
- [ ] **M11 Docs and final verification**
- [ ] **M12 Stretch**

## Current

Next: **M10** (compose images for api/worker/web, CI polish, healthchecks).
