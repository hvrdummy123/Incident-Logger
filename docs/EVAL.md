# Evaluation notes

## Demo split (measured 2026-11-14)

```bash
uv run traceiq eval run --suite demo --agents oracle,deterministic,latest_deploy
```

| Agent | service_top1 | category_ok | trigger_ok | n |
| --- | --- | --- | --- | --- |
| oracle | 1.00 | 1.00 | 1.00 | 3 |
| deterministic | 0.67 | 1.00 | 0.33 | 3 |
| latest_deploy | 0.33 | 1.00 | 0.33 | 3 |

Oracle = 100% on demos. Deterministic beats latest_deploy on service top-1. Cache stampede still fools both non-oracle agents (they pick `cart`).

## Dev split

```bash
uv run traceiq eval run --suite dev --agents oracle,deterministic,latest_deploy
```

n=2 (`db_pool_dev_100`, `unsolvable_dev_101`). Oracle abstains on unsolvable; deterministic does not.

## Held-out test split (frozen; run once 2026-11-14)

Scenario: `flag_flip_test_200` (feature flag on checkout). Do not retune agents against this file.

```bash
uv run traceiq eval run --suite test --agents oracle,deterministic,latest_deploy
```

| Agent | service_top1 | category_ok | trigger_ok | n |
| --- | --- | --- | --- | --- |
| oracle | 1.00 | 1.00 | 1.00 | 1 |
| deterministic | 1.00 | 1.00 | 1.00 | 1 |
| latest_deploy | 1.00 | 1.00 | 1.00 | 1 |

Small-sample (n=1). No bootstrap CI computed. Expand the frozen set before claiming generalization.

## Live LLM

No `ANTHROPIC_API_KEY` / OpenAI key present during this run. Live accuracy/cost/latency: **TODO(real-run)**.
