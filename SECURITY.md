# Security

Report suspected vulnerabilities privately. Do not open a public issue with exploit details.

## Scope

TraceIQ is read-only against telemetry by design. The agent never remediates production systems; suggested actions are text only.

## Defaults that matter

- **Tenant isolation is three layers:** app `workspace_id` filters, Postgres RLS on a non-superuser role, and a filesystem sandbox. Details and tests: `docs/THREAT_MODEL.md`.
- Redaction runs before any model egress (M6).
- `TRACEIQ_NO_EXTERNAL_LLM=1` fails closed (zero provider calls).
- Dataset paths are scoped under `data/<workspace_id>/` with canonicalization checks — `..` traversal cannot reach another company’s files.
- Audit log is hash-chained per workspace; UPDATE/DELETE are forbidden by DB triggers.
- Never run the API/worker as a DB superuser (compose user `traceiq` is for migrations only).

## Accepted risks

Document high-severity findings from `pip-audit` / `npm audit` / bandit here when we start accepting them with rationale. Currently none recorded.
