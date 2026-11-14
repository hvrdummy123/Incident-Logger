# ADR 0001: Modular monolith

## Context

TraceIQ has one data domain (incident telemetry + investigations) and a small team. Microservices would add network failure modes and duplicate auth/tenancy without buying independent scale yet.

## Decision

Ship one Python codebase as three processes (`api`, `worker`, `web` static) plus Postgres. Keep clear package boundaries (`ingest`, `store`, `analytics`, `agent`, `safety`) so a later split is possible.

## Alternatives

- Microservices from day one — rejected; ops cost dominates.
- Serverless functions per step — poor fit for durable multi-minute investigations.

## Consequences

Simple local compose story; shared transactions for jobs + audit. Workers scale horizontally via the Postgres queue before we need a broker.

## Revisit if

Ingest volume or tenant isolation forces separate deploy units, or the investigation worker's CPU profile fights the API's latency SLOs.
