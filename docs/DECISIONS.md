# Decisions

## Naming

- **Product name:** TraceIQ (user choice; replaces the prompt's "Sherlog").
- **Python import path / CLI:** `traceiq`.
- **PyPI distribution name (if we ever publish):** `traceiq-incident`.
  - Reason: `traceiq` on PyPI is already taken by an unrelated multi-agent influence library (later renamed Inflion). `traceiq-sdk` is also taken (OpenLLMetry wrapper). We are not forking either.
- **Env prefix:** `TRACEIQ_*` (e.g. `TRACEIQ_MODEL`, `TRACEIQ_NO_EXTERNAL_LLM`).
- **Prometheus metric prefix:** `traceiq_`.

## Authorship

- Built from an empty directory. No clone of Killkanacode/sherlog, GetSherlog/*, kqiu10/Sherlog, or any TraceIQ GitHub repo.
- Spec source: local `incident_agent_prompt.md` only.

## Preflight toolchain (M0)

| Tool | Version found |
|---|---|
| Python (system) | 3.13.5 |
| Python (project target via uv) | 3.12.13 (`uv` managed cpython-3.12) |
| uv | present (`/opt/homebrew/bin/uv`) |
| Node | v22.23.3 |
| npm | 10.9.9 |
| Docker | 29.8.2 |
| Postgres (client) | 17.10 (Homebrew) |
| git | 2.54.0 |

I pinned the project to **Python 3.12** as the prompt specifies, even though the shell default is 3.13. Docker Compose will bring up Postgres for integration tests; system `psql` is available as a client.

## Local Postgres port

Compose publishes Postgres on **host port 55432** (`55432:5432`) because 5432 is Homebrew Postgres and 5433 is another local compose stack. Default `TRACEIQ_DATABASE_URL` uses 55432. CI still uses 5432 (GitHub service container).
