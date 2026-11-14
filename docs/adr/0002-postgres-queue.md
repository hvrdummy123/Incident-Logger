# ADR 0002: Postgres as the job queue

## Context

Investigations and ingest jobs need durable leases, retries, and dead-lettering. A separate broker (Redis/Kafka) adds another moving part for a single-node design center.

## Decision

Use Postgres with `FOR UPDATE SKIP LOCKED`, lease timestamps, attempt counters, and exponential backoff. Workers commit the claim before running work so a crash mid-handler does not rewind the attempt count.

## Alternatives

- Redis lists / Streams — faster, but another dependency and weaker multi-tenant audit story.
- Kafka — right for multi-GB/s ingest later; overkill now.

## Consequences

One operational surface with the metadata DB. At high queue depth, workers contend on the jobs index — that is the signal to revisit a broker (see `docs/SCALING.md` later).

## Revisit if

Queue depth or claim latency becomes the bottleneck under realistic multi-tenant load.
