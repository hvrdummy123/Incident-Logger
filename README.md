# TraceIQ

TraceIQ ingests an incident’s telemetry (logs, metrics, traces, change events), builds a timeline and suspect ranking with explainable algorithms, then runs a read-only LLM investigator that produces a postmortem-style root-cause report where every claim cites clickable evidence. It abstains when the evidence is thin.

## Try it in 3 minutes

```bash
cp .env.example .env
make setup
make up
uv run traceiq doctor
uv run traceiq serve   # API on :8000
cd web && npm run dev  # UI on :5173 (proxies /v1)
```

## How this was built

Built with AI coding agents under my specification, with my review and testing. Details: TODO(human).

## Naming

Product name is **TraceIQ**. The installable distribution is `traceiq-incident` because the PyPI name `traceiq` is already taken by an unrelated project. Import and CLI remain `traceiq`.

## Status

**M0–M9 core** landed (API + UI: incidents, BYO wizard, investigation, report). See `docs/PLAN.md` and `docs/HANDOFF.md`.

## License

Apache-2.0
