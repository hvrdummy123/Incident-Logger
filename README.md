# TraceIQ

**Incident investigation that stays honest when the data is messy.**

TraceIQ turns an outage’s telemetry — especially raw logs — into a ranked set of suspects and a postmortem-style report. It prefers explainable analytics over a black-box “AI said so,” cites what it used, asks for missing signals when the picture is incomplete, and abstains instead of inventing a tidy root cause.

---

## What problem it solves

During a real outage you rarely have perfect metrics, traces, and change tickets lined up. You have logs (often incomplete), overlapping failures, and decoy deploys. Engineers still need a working theory fast: which services look hot, what changed nearby, and what would make the call stronger.

TraceIQ is built for that workflow — not for replacing your pager or observability stack.

## What it does

1. **Ingest** — Upload BYO logs (JSONL) or load a demo incident. Sensitive values are redacted before any model path.
2. **Brief** — Deterministic analytics build an onset estimate, new/high error templates, change proximity, anomaly scores, and a **suspect ranking** with contribution reasons.
3. **Investigate** — A read-only agent loop (mock or live LLM) uses tools against that briefing; it cannot mutate prod.
4. **Report** — A narrative investigation report: multi-factor lean when several services are hot, impact/timeline, contributing factors, ruled-out decoys, suggested actions, **data gaps**, and **“what would sharpen this.”**
5. **Verify** — Claims are checked for evidence citations; soft gaps lower confidence instead of silently shipping a fake certainty.

The web UI shows investigation steps, swimlanes / service graph, interactive charts (suspect scores, confidence, log-derived error rates), and an exportable report.

## Who it’s for

- On-call / SRE reviewing a messy window of logs  
- Teams demoing “AI-assisted RCA” with auditability and multi-tenant safety in mind  
- Portfolio / interview walkthroughs of a full-stack agentic systems project  

## Architecture (short)

Modular monolith: **FastAPI API**, **worker**, **React (Vite) UI**, **Postgres** with row-level security (`traceiq_app`), Parquet/DuckDB-oriented log store, safety (redaction + egress controls) around optional LLM calls.

```text
  Web / CLI / alerts
          │
       FastAPI
       /      \
  Postgres    Parquet/data
  (RLS)         │
       \      /
        Worker + agent tools
              │
     optional redacted LLM
```

More detail: [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) (why this design) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (flows).

## Try it locally

**Prerequisites:** Python 3.12, [uv](https://github.com/astral-sh/uv), Node.js, Docker.

```bash
cp .env.example .env
make setup                          # uv sync + npm install

docker compose up -d postgres migrate   # Postgres on host :55432

export TRACEIQ_DATABASE_URL=postgresql+psycopg://traceiq_app:traceiq@127.0.0.1:55432/traceiq
export TRACEIQ_MIGRATE_URL=postgresql+psycopg://traceiq:traceiq@127.0.0.1:55432/traceiq
export TRACEIQ_JWT_SECRET=dev-local-jwt-secret-change-me-32b
export TRACEIQ_REDACTION_KEY=dev-local-redaction-key
export TRACEIQ_MODEL=mock:mock-v1
export TRACEIQ_NO_EXTERNAL_LLM=1
export TRACEIQ_DATA_DIR=./data

uv run traceiq seed-user \
  --email demo@traceiq.local \
  --password demo-demo-demo \
  --workspace local

# Terminal 1 — API
uv run traceiq serve --host 127.0.0.1 --port 8000

# Terminal 2 — UI
cd web && npm run dev
```

- UI: http://127.0.0.1:5173  
- API: http://127.0.0.1:8000  
- Login: `demo@traceiq.local` / `demo-demo-demo`

Optional: `uv run traceiq doctor` · full stack: `docker compose up -d --build` (UI often on :8080).

### Sample logs

| File | What you’ll see |
|------|-----------------|
| `samples/byo/outage_2024-11-14.jsonl` | Smaller single-lean demo |
| `samples/byo/prod_slice_2024-11-14.jsonl` | Large multi-fault industry-style slice |

In the UI: **Bring your own** → upload → run investigation → open the report (charts + gaps).

## Safety & tenancy

- JWT auth + workspace RBAC  
- Postgres **RLS** so tenants don’t see each other’s data  
- Redaction before egress; optional `TRACEIQ_NO_EXTERNAL_LLM=1` for offline / mock-only runs  
- Investigation tools are **read-only**

## Project layout

```text
src/traceiq/     API, agent, analytics, ingest, safety, auth, DB
web/             React investigation + report UI
samples/         Demo and BYO log files
docs/            Architecture, runbook, handoff, API
portfolio/       Diagram / GIF / short video assets (optional)
```

## Naming

Product name: **TraceIQ**.  
PyPI distribution name: `traceiq-incident` (the name `traceiq` is taken).  
Import and CLI stay `traceiq`.

## Status

Milestones **M0–M11** are in place (compose, UI, measured notes in [`REPORT.md`](REPORT.md)). See also [`docs/HANDOFF.md`](docs/HANDOFF.md) and [`docs/PLAN.md`](docs/PLAN.md).

## How this was built

Built and maintained by **hvrdummy123**.

## License

Apache-2.0
