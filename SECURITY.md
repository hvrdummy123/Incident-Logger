# Security

Report suspected vulnerabilities privately. Do not open a public issue with exploit details.

## Scope

TraceIQ is read-only against telemetry by design. The agent never remediates production systems; suggested actions are text only.

## Defaults that matter

- Redaction runs before any model egress.
- `TRACEIQ_NO_EXTERNAL_LLM=1` fails closed (zero provider calls).
- Dataset paths are scoped under `data/<workspace_id>/` with canonicalization checks.
- Audit log is hash-chained per workspace; UPDATE/DELETE are forbidden by DB triggers.

## Accepted risks

Document high-severity findings from `pip-audit` / `npm audit` / bandit here when we start accepting them with rationale. Currently none recorded.
