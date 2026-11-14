# TraceIQ — System Architecture & Design

This document explains **what the system looks like**, **why it is shaped this way**, **what problem that shape solves**, **where it is strong**, and **how it can improve**. For diagrams of request flows only, see also [`ARCHITECTURE.md`](ARCHITECTURE.md). For individual decision log entries, see [`DECISIONS.md`](DECISIONS.md).

---

## 1. Problem this design solves

### The operational problem

When production breaks, responders face:

| Reality | Design implication |
| --- | --- |
| Logs are incomplete, rotated, or sampled | Summarize what *is* known; ask for what is missing |
| Multiple services fail at once | Support **multi-factor** findings, not one forced root cause |
| Nearby deploys create decoys | Rank with explainable signals; explicitly rule out weak proximity |
| “AI RCA” tools invent tidy stories | Separate **deterministic briefing** from narrative; **verify** citations |
| Telemetry may leave the trust boundary | Redact before egress; allow offline / mock-only mode |
| Several teams share one platform | Multi-tenant auth + Postgres **RLS** from day one |

TraceIQ is not a replacement for Datadog/PagerDuty. It is an **investigation assistant**: ingest a messy window → produce a defensible working theory (or an honest abstention).

### The product problem the architecture must support

- Ship a **credible demo** (BYO logs, investigation UI, report) without a microservices fleet.
- Keep seams clear so a later split (API / worker / analytics service) does not rewrite the domain.
- Stay **safe by default** for enterprise demos: tenancy, redaction, read-only tools, budgets.

---

## 2. System architecture (current)

### 2.1 High-level view

```text
┌─────────────┐  ┌──────────┐  ┌──────────────┐
│  Web (Vite) │  │ CLI      │  │ Alert webhook│
└──────┬──────┘  └────┬─────┘  └──────┬───────┘
       │              │               │
       └──────────────┼───────────────┘
                      ▼
              ┌───────────────┐
              │  FastAPI API  │◄── JWT + workspace RBAC
              └───────┬───────┘
          ┌───────────┼───────────┐
          ▼           ▼           ▼
    ┌──────────┐ ┌─────────┐ ┌────────────────┐
    │ Postgres │ │ Parquet │ │ Optional LLM   │
    │ + RLS    │ │ / data  │ │ (redacted only)│
    └────┬─────┘ └────┬────┘ └────────▲───────┘
         │            │               │
         └─────┬──────┘               │
               ▼                      │
         ┌──────────┐    agent tools  │
         │  Worker  │─────────────────┘
         └──────────┘
```

**Processes today**

| Process | Role |
| --- | --- |
| `api` | Auth, incidents, BYO upload/preview, start investigation, reports, SSE steps |
| `worker` | Queue leases for longer jobs (handlers evolving; mock investigations often run sync in API for demos) |
| `web` | React UI: login, incidents, BYO wizard, investigation panes, interactive report charts |
| `postgres` | Metadata, tenancy, jobs, audit; RLS via `traceiq_app` |

**Package seams** (same repo, clear boundaries): `ingest` → `store` → `analytics` → `agent` + `safety`; `auth` / `tenancy` / `queue` cross-cut.

### 2.2 Investigation data path (the design that matters)

```text
  Raw logs (BYO / demo)
           │
           ▼
  Parse + normalize ──► redaction preview
           │
           ▼
  Deterministic briefing
    • onset heuristic
    • templates / anomalies
    • change proximity
    • suspect ranking + contributions
    • error_series (for charts)
           │
           ▼
  Agent loop (read-only tools)
    get_briefing · top_templates · recent_changes · …
           │
           ▼
  Narrative report (+ viz payload)
           │
           ▼
  Verify citations ──► soft gaps / confidence cap / abstain on hard fails
           │
           ▼
  UI: report + charts + “what would sharpen this”
```

**Core invariant:** ranking and structure come from **analytics**; language and synthesis come from the **narrative / model** layer; **verify** keeps the model honest.

### 2.3 Trust and tenancy

```text
  Request
    → JWT + workspace
    → DB session as traceiq_app (RLS)
    → Untrusted log text scanned / never treated as instructions
    → Redaction map before any external model call
    → Egress allowlist + spend budget
```

Tools exposed to the agent are **read-only**. The agent cannot restart services, patch configs, or write to customer systems.

---

## 3. Why this specific design was chosen

### 3.1 Modular monolith (not microservices)

| Alternative | Why not (yet) |
| --- | --- |
| Separate ingest / analytics / agent services | Extra ops cost; same team; early product |
| Serverless-only | Awkward long investigations + local demo story |
| Single process with everything in the request | Blocks workers, harder timeouts / resume |

**Choice:** one codebase, **three processes** (`api` / `worker` / `web`) + Postgres. Package boundaries are the future service boundaries.

**Solves:** ship fast, demo locally, keep a path to scale-out without a rewrite.

### 3.2 Deterministic briefing before the LLM

| Alternative | Why not |
| --- | --- |
| Dump raw logs into the model | Cost, context limits, hallucination, no explainability |
| Pure rules with no narrative | Hard to communicate multi-fault nuance to humans |

**Choice:** analytics produce a compact briefing (suspects, templates, changes, gaps). The model (or mock narrative builder) **interprets** that briefing.

**Solves:** explainable scores, reproducible offline demos (`mock:mock-v1`), cheaper tokens, better behavior on imperfect logs.

### 3.3 Honest multi-factor + abstain

| Alternative | Why not |
| --- | --- |
| Always pick top-1 service | Wrong for cascading / concurrent faults |
| Always “confident” prose | Erodes trust when data is thin |

**Choice:** detect multi-fault when secondary scores are close; emit contributing factors + open questions; abstain or lower confidence when verification fails hard / soft.

**Solves:** the real outage shape companies actually have — messy, overlapping, incomplete.

### 3.4 Postgres RLS + app role

| Alternative | Why not |
| --- | --- |
| App-layer filters only | Easy to forget a `WHERE workspace_id` |
| One DB per tenant early | Ops heavy for a demo / MVP |

**Choice:** shared DB, `traceiq_app` with RLS, migrate URL for bootstrap/seed.

**Solves:** multi-tenant safety as a design property, not a later bolt-on.

### 3.5 Parquet / file store for bulk logs

| Alternative | Why not |
| --- | --- |
| All events in Postgres | Expensive for large BYO slices; poor analytics scan cost |
| Only object storage APIs | Harder for local/dev and single-compose demos |

**Choice:** dataset metadata in Postgres; bulk lines in `data/` (Parquet-oriented). Briefing for BYO can also be built directly from uploaded text for the demo path.

**Solves:** industry-scale log files without turning Postgres into a log warehouse.

### 3.6 Safety as a first-class package

Redaction, injection scan, egress gateway, and budgets live in `safety`, not sprinkled in route handlers.

**Solves:** “we’ll add security later” — the portfolio and enterprise story both need this visible.

### 3.7 React SPA + FastAPI API

Thin UI over a stable `/v1` API keeps CLI, webhooks, and UI on the same contracts. Vite proxy in dev; static nginx (or compose web) in prod-like stacks.

**Solves:** one backend for humans and machines; interactive report charts without baking a BI tool into Python templates.

---

## 4. Where this design is advantageous

| Advantage | Why it matters |
| --- | --- |
| **Trustworthy RCA narrative** | Citations + verify + data-gap asks beat “chatbot postmortem” |
| **Works on imperfect data** | Partial logs still produce a useful summary and ask list |
| **Demoable offline** | Mock provider + deterministic briefing = no API keys required |
| **Enterprise-shaped early** | RLS, RBAC, redaction, egress — interview / design-review friendly |
| **Cheap to evolve** | Clear packages; worker already separated for long jobs |
| **Human-in-the-loop** | Feedback on reports; suggested actions are labeled as suggestions |
| **Interactive explainability** | Suspect bars, error-rate series, timeline marks share the briefing |

---

## 5. Tradeoffs (honest)

| Tradeoff | Consequence |
| --- | --- |
| Sync mock investigation in API | Simple demos; less realistic under load than always-async worker |
| Log-derived “metrics” | Charts are error rates from logs, not golden APM signals |
| Mock narrative quality | Strong structure; live LLM will improve prose, not replace analytics |
| Large BYO briefing | Full-file parse can be slow on ~25MB+ slices |
| Modular monolith | Still one deploy unit until you actually split services |

---

## 6. How we can improve

Prioritized directions — not a commitment order.

### Near-term (product depth)

1. **Always-async investigations** — enqueue every run; SSE/DB steps as source of truth; API never blocks on 140k-line briefings.
2. **Real evidence excerpts** — citation drawer shows highlighted log lines / template ids, not placeholders.
3. **Faster briefing** — streaming parse, sampling strategy for preview vs full investigate, DuckDB pushdown on Parquet.
4. **Richer graph** — dependency edges from spans/gateway logs; cascade visualization (cause vs blast radius).
5. **Live LLM path** — same briefing + verify; A/B mock vs provider on held-out scenarios ([`EVAL.md`](EVAL.md)).

### Mid-term (platform)

6. **Split worker-heavy paths** — analytics and agent as separate deployables behind the same package APIs.
7. **Object storage** — S3-compatible dataset backend for multi-node.
8. **Change / metrics / traces adapters** — optional connectors so “what would sharpen this” can be satisfied in-product.
9. **Playwright + a11y** — harden UI for real on-call use.
10. **Held-out eval growth** — more multi-fault and decoy scenarios; track top-1 / multi-factor / abstain rates.

### Longer-term (enterprise)

11. **SSO / SCIM**, finer audit export, retention policies per workspace.  
12. **Policy packs** — per-tenant allowlists for model hosts and data classes.  
13. **Collaborative postmortem** — shared annotations on the same report timeline.

---

## 7. Design principles (summary)

1. **Analytics first, language second** — scores must be explainable without the model.  
2. **Honesty over neatness** — multi-factor, gaps, and abstain beat a wrong single cause.  
3. **Safety by construction** — RLS, redaction, read-only tools, budgets.  
4. **Seams before services** — modular monolith until scale forces a split.  
5. **Demo = production shape** — same path for mock and live LLM; only the provider changes.

---

## 8. Related docs

| Doc | Contents |
| --- | --- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Component and sequence diagrams |
| [`THREAT_MODEL.md`](THREAT_MODEL.md) | Threats and mitigations |
| [`RUNBOOK.md`](RUNBOOK.md) | Operate / break-glass |
| [`BRING_YOUR_OWN_DATA.md`](BRING_YOUR_OWN_DATA.md) | BYO upload expectations |
| [`REPORT.md`](../REPORT.md) | Measured status of the build |
| [`../README.md`](../README.md) | Product overview + run commands |
