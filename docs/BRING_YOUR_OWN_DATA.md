# Bring your own data

## UI wizard

1. Sign in (local JWT).
2. **Bring your own** → choose a text log (≤2 MB for browser preview).
3. Read the **parse report** (format, unparsed examples, services, skew warnings).
4. Review **redaction preview**; leave “Deterministic only, no model” on unless you intentionally allow egress.
5. Set title/severity → create incident → run investigation (mock today).

Binary files with null bytes are rejected with a readable error.

## CLI

```bash
uv run traceiq ingest path/to/file.log --dry-run
uv run traceiq redact-preview path/to/file.log
```

Materialized parquet ingest uses the same pipeline when not dry-run (workspace + dataset id required).

## Privacy banner meaning

- **Deterministic only:** ranking/templates only; no model call.
- **External model: redacted:** payloads pass the egress gateway; secrets should be placeholderized; `NO_EXTERNAL_LLM=1` fails closed.
