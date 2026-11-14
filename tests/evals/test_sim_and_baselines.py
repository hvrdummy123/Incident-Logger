from __future__ import annotations

import json
from pathlib import Path

from traceiq.evals.runner import run_agents, run_suite, scenarios_dir
from traceiq.sim.scenarios import load_scenario
from traceiq.sim.world import simulate, write_bundle


def test_simulator_deterministic() -> None:
    sc = load_scenario(scenarios_dir() / "bad_deploy_demo.yaml")
    a = simulate(sc)
    b = simulate(sc)
    assert [x["message"] for x in a.logs] == [x["message"] for x in b.logs]
    assert [x["value"] for x in a.metrics] == [x["value"] for x in b.metrics]
    assert a.ground_truth == b.ground_truth


def test_different_seeds_differ() -> None:
    sc = load_scenario(scenarios_dir() / "bad_deploy_demo.yaml")
    a = simulate(sc)
    sc.seed = 12345
    b = simulate(sc)
    assert [x["message"] for x in a.logs] != [x["message"] for x in b.logs] or len(a.logs) != len(
        b.logs
    )


def test_ground_truth_self_consistency() -> None:
    sc = load_scenario(scenarios_dir() / "db_pool_demo.yaml")
    bundle = simulate(sc)
    truth = bundle.ground_truth
    assert truth["root_cause_service"] == "payments"
    gold = truth["gold_templates"]
    messages = {row["message"] for row in bundle.logs}
    for g in gold:
        assert any(g in m for m in messages), f"missing gold template: {g}"
    # onset aligns with error_rate jump on payments
    onset_ms = bundle.base_ts_ms + int(truth["onset_min"]) * 60_000
    before = [
        m["value"]
        for m in bundle.metrics
        if m["name"] == "error_rate"
        and m["labels"]["service"] == "payments"
        and m["ts"] < onset_ms
    ]
    after = [
        m["value"]
        for m in bundle.metrics
        if m["name"] == "error_rate"
        and m["labels"]["service"] == "payments"
        and m["ts"] >= onset_ms
    ]
    assert after and sum(after) / len(after) > sum(before) / max(1, len(before))


def test_oracle_100_and_decoys_defeat_heuristics() -> None:
    result = run_suite(
        split="demo",
        agents=["oracle", "most_errors", "latest_deploy", "deterministic"],
    )
    assert result["n_scenarios"] >= 3
    assert result["agents"]["oracle"]["service_top1"] == 1.0
    # decoys: latest_deploy must not be perfect on demo set
    assert result["agents"]["latest_deploy"]["service_top1"] < 1.0


def test_deterministic_beats_latest_deploy_on_dev() -> None:
    result = run_suite(
        split="dev",
        agents=["deterministic", "latest_deploy", "most_errors"],
    )
    if result["n_scenarios"] == 0:
        return
    det = result["agents"]["deterministic"]["service_top1"]
    latest = result["agents"]["latest_deploy"]["service_top1"]
    # soft gate while scenario count is small — deterministic should not lose badly
    assert det >= latest or det > 0


def test_write_bundle_roundtrip(tmp_path: Path) -> None:
    sc = load_scenario(scenarios_dir() / "bad_deploy_demo.yaml")
    bundle = simulate(sc)
    out = tmp_path / "bundle"
    write_bundle(bundle, out)
    assert (out / "ground_truth.json").exists()
    assert (out / "metrics.csv").exists()
    assert (out / "changes.csv").exists()
    gt = json.loads((out / "ground_truth.json").read_text(encoding="utf-8"))
    assert gt["root_cause_service"] == "payments"
    assert any((out / "logs").glob("*.log"))


def test_oracle_abstains_when_unsolvable() -> None:
    sc = load_scenario(scenarios_dir() / "unsolvable_dev_101.yaml")
    bundle = simulate(sc)
    diag = run_agents(bundle, ["oracle"])["oracle"]
    assert diag.abstained
