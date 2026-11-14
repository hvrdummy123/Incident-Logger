# Human test checklist

Run by hand after the stack is up. Do not invent results here.

1. Fresh clone → `make setup test` → note skips.
2. `docker compose up` → UI → login → load demo 1 → mock investigation → citations open real evidence.
3. Grade demos 2 and 3 blind against `demo/answers/`.
4. BYO with authorized real logs per `BRING_YOUR_OWN_DATA.md`.
5. Garbage inputs: binary, empty, huge, zip bomb sample, CRLF, mixed TZs.
6. Plant injection + fake card number; confirm flag + redaction in egress ledger.
7. `kill -9` worker mid-run; stop Postgres briefly; watch recovery.
8. Cross-workspace access attempts via UI and API.
9. `TRACEIQ_NO_EXTERNAL_LLM=1` → zero provider calls, labeled deterministic report.
10. Audit chain verify, then tamper a row and verify again.
11. Failure gallery honesty; every README number exists in a run log.
12. Mobile width + keyboard-only + dark/light.
13. Fill `HUMAN_NOTES.md`; walk `DEFENSE_NOTES.md` out loud.
14. Grep for secrets, absolute paths, stray hype words.
