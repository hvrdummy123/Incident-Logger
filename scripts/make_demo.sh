#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

uv run python - <<'PY'
from pathlib import Path
import json
from traceiq.sim.scenarios import load_scenario
from traceiq.sim.world import simulate, write_bundle

root = Path(".")
mapping = {
    "bad_deploy_demo": "demo/incident-1-bad-deploy",
    "db_pool_demo": "demo/incident-2-db-pool",
    "cache_stampede_demo": "demo/incident-3-cache-stampede",
}
scenarios = Path("src/traceiq/sim/scenarios")
answers = Path("demo/answers")
answers.mkdir(parents=True, exist_ok=True)

titles = {
    "bad_deploy_demo": "Checkout and payments errors after a release window",
    "db_pool_demo": "Checkout 5xx with slow payments and a quiet inventory",
    "cache_stampede_demo": "Catalog latency spike and cache weirdness",
}

for sid, out in mapping.items():
    path = scenarios / f"{sid}.yaml"
    sc = load_scenario(path)
    bundle = simulate(sc)
    out_dir = root / out
    write_bundle(bundle, out_dir, mixed_formats=True)
    # Keep demos spoiler-free — move ground truth next to answer keys
    gt_path = out_dir / "ground_truth.json"
    if gt_path.exists():
        gt_path.rename(answers / f"{out_dir.name}.ground_truth.json")
    (out_dir / "README.md").write_text(
        f"# {out_dir.name}\n\n"
        f"{titles[sid]}\n\n"
        "Load this bundle into TraceIQ and investigate. "
        "Answer key is intentionally not here — see demo/answers/ after you grade yourself.\n",
        encoding="utf-8",
    )
    print(f"wrote {out_dir} logs={len(bundle.logs)} metrics={len(bundle.metrics)}")

(answers / "incident-1-bad-deploy.md").write_text(
    "# Answer: incident-1-bad-deploy\n\n"
    "- Root cause service: **payments**\n"
    "- Category: bad_deploy\n"
    "- Trigger: payments deploy shortly before onset\n"
    "- Decoy: cart / recs deploys\n",
    encoding="utf-8",
)
(answers / "incident-2-db-pool.md").write_text(
    "# Answer: incident-2-db-pool\n\n"
    "- Root cause service: **payments** (pool exhaustion on payments-db)\n"
    "- Category: resource_exhaustion\n"
    "- Inventory logs intentionally missing\n"
    "- Decoy: innocent cart deploy + hourly batch\n",
    encoding="utf-8",
)
(answers / "incident-3-cache-stampede.md").write_text(
    "# Answer: incident-3-cache-stampede\n\n"
    "- Root cause service: **redis-cache**\n"
    "- Category: cache_stampede\n"
    "- Look for cache miss storm + catalog-db load\n",
    encoding="utf-8",
)
print("demo answers written")
PY
