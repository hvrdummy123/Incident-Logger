.PHONY: setup test lint e2e demo up down bench eval doctor

PYTHON ?= uv run
PYTEST ?= uv run pytest

setup:
	uv sync --python 3.12 --extra dev
	cd web && npm install

test:
	$(PYTEST) -n auto --ignore=tests/perf --ignore=tests/chaos --ignore=tests/e2e

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy src/traceiq
	cd web && npx tsc --noEmit || true

e2e:
	$(PYTEST) tests/e2e -m "not perf"

demo:
	uv run traceiq demo list

up:
	docker compose up -d --build

down:
	docker compose down

bench:
	./scripts/bench.sh

eval:
	uv run traceiq eval run --suite dev --agents deterministic --provider mock

doctor:
	uv run traceiq doctor
