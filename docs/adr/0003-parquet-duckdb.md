# ADR 0003: Parquet + DuckDB for telemetry

## Context

Incident bundles are immutable and query-heavy. We need fast local analytics without running Elasticsearch/ClickHouse for a single-node design center.

## Decision

Write telemetry as Parquet under `data/<workspace_id>/datasets/<id>/`, query with in-process DuckDB (read-only views). Rollups (`template_counts_1m`) are written at ingest time.

## Alternatives

- Postgres for raw logs — poor fit past tens of millions of lines.
- ClickHouse / ES — correct at scale; heavy ops for this stage.

## Consequences

Simple deploy; content-addressed datasets. Scale-out later maps to object storage + DuckDB/Trino workers.

## Revisit if

Interactive queries over multi-TB tenants become a product requirement.
