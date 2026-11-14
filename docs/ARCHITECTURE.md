# Architecture

Modular monolith: one Python codebase, three processes (`api`, `worker`, `web` static), plus Postgres. Seams are package boundaries (`ingest`, `store`, `analytics`, `agent`, `safety`, `queue`) so a later split is possible without rewriting the domain.

## Context

```mermaid
flowchart LR
  User[On-call / reviewer] --> Web[web nginx]
  User --> CLI[traceiq CLI]
  Alert[Pager / webhook] --> API
  Web --> API[api FastAPI]
  CLI --> API
  CLI --> Data[(data/ parquet)]
  API --> PG[(Postgres + RLS)]
  API --> Data
  Worker[worker] --> PG
  Worker --> Data
  API -. optional redacted .-> Model[LLM provider]
```

```
                 alert webhook / uploads / CLI
                           |
                     +-----+------+
                     |    api     |
                     +--+------+--+
                        |      |
                   +----v--+  +v--------+
                   |postgres|  | parquet |
                   +----+---+  +----+----+
                        |           |
                     +--v-----------v--+
                     |     worker      |
                     +--------+--------+
                              |
                     (optional egress)
```

## Components

```mermaid
flowchart TB
  subgraph processes
    API[api]
    W[worker]
    UI[web]
  end
  subgraph packages
    ingest
    store
    analytics
    agent
    safety
    queue
    auth
    tenancy
  end
  UI --> API
  API --> ingest
  API --> agent
  API --> safety
  API --> auth
  API --> tenancy
  W --> queue
  W --> agent
  ingest --> store
  analytics --> store
  agent --> safety
```

## Sequence: ingest

```mermaid
sequenceDiagram
  actor U as User/CLI
  participant API
  participant Detect as ingest.detect
  participant Parse as ingest.parsers
  participant Store as store/parquet
  participant PG as Postgres
  U->>API: upload / dry-run
  API->>Detect: sample lines
  Detect-->>API: format + confidence
  API->>Parse: iter_parsed
  Parse-->>API: events + parse report
  alt dry-run
    API-->>U: parse report JSON
  else materialize
    API->>Store: write logs.parquet
    API->>PG: dataset row + audit
    API-->>U: dataset_id
  end
```

ASCII:

```
CLI/UI -> detect(format) -> parse(lines) -> build_report
                              |
                    dry-run?--+--> return report
                              |
                              +--> parquet + manifest + DB row
```

## Sequence: investigation (crash + resume — intended)

```mermaid
sequenceDiagram
  actor U as Investigator
  participant API
  participant PG
  participant W as Worker
  participant Agent
  U->>API: POST /incidents/{id}/investigations
  API->>PG: insert investigation + job
  API-->>U: investigation_id
  W->>PG: claim job (lease)
  Note over W,Agent: Today the API runs mock sync;<br/>worker handlers are stubs (M10).
  W->>Agent: run_investigation
  Agent-->>W: steps / report
  W->>PG: investigation_steps + report
  Note over W: If worker dies mid-run,<br/>lease expires and another worker claims.
  U->>API: GET .../events (SSE)
  API-->>U: steps (cache / DB)
```

## Sequence: alert webhook

```mermaid
sequenceDiagram
  participant Hook as Alert source
  participant API
  participant PG
  Hook->>API: POST /v1/webhooks/alerts + API key + Idempotency-Key
  API->>PG: lookup key hash + workspace
  alt duplicate key
    API-->>Hook: 200 duplicate
  else new
    API->>PG: create incident + audit
    API-->>Hook: 201 incident_id
  end
```

## What happens when X fails

| Failure | Behavior |
| --- | --- |
| Postgres down | `/readyz` fails; writes error; worker idles |
| Worker killed | Lease expires; job reclaimed (when handlers enqueue work) |
| Model timeout | Egress/provider error → degrade / abstain path in runtime |
| Bad upload | Preview returns 400 with readable detail (binary/null bytes) |
| Duplicate webhook | Same Idempotency-Key → `status=duplicate`, no second incident |
