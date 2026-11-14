# TraceIQ API / worker image (multi-stage, non-root).
FROM python:3.12-slim-bookworm AS build

WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /usr/local/bin/uv

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN uv sync --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && useradd --create-home --uid 10001 --shell /usr/sbin/nologin traceiq

WORKDIR /app
COPY --from=build /src/.venv /app/.venv
COPY --from=build /src/src /app/src
COPY alembic.ini /app/alembic.ini
COPY scripts /app/scripts
COPY pyproject.toml /app/pyproject.toml

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    TRACEIQ_DATA_DIR=/data

COPY scripts/docker-entrypoint.sh /app/docker-entrypoint.sh
# shell scripts need execute bit; keep owned by non-root
USER root
RUN chmod +x /app/docker-entrypoint.sh \
  && mkdir -p /data \
  && chown -R traceiq:traceiq /app /data
USER traceiq

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/v1/healthz || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "traceiq.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
