#!/bin/sh
set -eu
# Optional one-shot migrations (compose prefers the dedicated migrate service).
if [ "${TRACEIQ_RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Running Alembic migrations…"
  alembic upgrade head
fi
exec "$@"
