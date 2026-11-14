"""OpenTelemetry + Prometheus hooks for TraceIQ itself.

NOTE: exporters are optional at import time; doctor reports whether OTLP is configured.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

investigation_duration = Histogram(
    "traceiq_investigation_duration_seconds",
    "Wall time of an investigation",
    buckets=(5, 15, 30, 60, 90, 120, 180, 300, 600),
)
investigation_cost = Histogram(
    "traceiq_investigation_cost_usd",
    "Estimated USD cost of an investigation",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
tokens_total = Counter(
    "traceiq_tokens_total",
    "Tokens consumed by model calls",
    ["direction"],  # in|out
)
outcome_total = Counter(
    "traceiq_outcome_total",
    "Investigation outcomes",
    ["outcome"],
)
jobs_queue_depth = Histogram(
    "traceiq_jobs_queue_depth",
    "Observed queue depth samples",
    buckets=(0, 1, 2, 5, 10, 25, 50, 100, 250),
)
jobs_failed_total = Counter("traceiq_jobs_failed_total", "Jobs moved to dead-letter")
ingest_lines_total = Counter(
    "traceiq_ingest_lines_total",
    "Log lines ingested",
    ["result"],  # parsed|unparsed
)
model_call_errors_total = Counter("traceiq_model_call_errors_total", "Provider call failures")
egress_blocked_total = Counter(
    "traceiq_egress_blocked_total",
    "Egress gateway blocks",
    ["reason"],
)
