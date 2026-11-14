"""Run baseline agents against simulator scenarios."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from traceiq.analytics.briefing import build_briefing
from traceiq.analytics.changes import ChangeEvent
from traceiq.evals.baselines import (
    Diagnosis,
    deterministic_agent,
    latest_deploy_agent,
    most_errors_agent,
    oracle_agent,
    random_agent,
)
from traceiq.evals.metrics import Score, aggregate, score_diagnosis
from traceiq.sim.scenarios import Scenario, list_scenarios, load_scenario
from traceiq.sim.topology import SERVICES
from traceiq.sim.world import SimBundle, simulate


def scenarios_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "sim" / "scenarios"


def load_split(split: str, directory: Path | None = None) -> list[Scenario]:
    directory = directory or scenarios_dir()
    out = []
    for path in list_scenarios(directory):
        sc = load_scenario(path)
        if split == "all" or sc.split == split or (split == "demo" and sc.split == "demo"):
            out.append(sc)
    return out


def bundle_to_briefing(bundle: SimBundle) -> dict[str, Any]:
    # metric series: service.error_rate
    series: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for m in bundle.metrics:
        if m["name"] != "error_rate":
            continue
        svc = m["labels"]["service"]
        series[f"{svc}.error_rate"].append((int(m["ts"]), float(m["value"])))
    for k in series:
        series[k].sort()

    # templates from log messages
    first_seen: dict[tuple[str, str], int] = {}
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in bundle.logs:
        key = (str(row["service"]), str(row["message"]))
        ts = int(row["ts"])
        counts[key] += 1
        first_seen[key] = min(first_seen.get(key, ts), ts)

    onset_ms = bundle.base_ts_ms + int(bundle.ground_truth.get("onset_min", 0)) * 60_000
    templates = []
    for (svc, msg), fs in first_seen.items():
        before = sum(
            1
            for row in bundle.logs
            if row["service"] == svc and row["message"] == msg and int(row["ts"]) < onset_ms
        )
        after = counts[(svc, msg)] - before
        templates.append(
            {
                "template_id": f"tpl_{hash(msg) & 0xFFFFFFFF:x}",
                "service": svc,
                "pattern": msg,
                "first_seen": fs,
                "count_before": before,
                "count_after": after,
                "count": counts[(svc, msg)],
            }
        )

    changes = [
        ChangeEvent(
            id=str(c["id"]),
            ts_ms=int(c["ts_ms"]),
            kind=str(c["kind"]),
            service=str(c["service"]),
            description=str(c.get("description") or ""),
        )
        for c in bundle.changes
    ]

    edges: list[tuple[str, str, bool]] = []
    for sp in bundle.spans:
        peer = (sp.get("attrs") or {}).get("peer.service")
        if peer:
            edges.append((str(sp["service"]), str(peer), sp.get("status") == "ERROR"))

    briefing = build_briefing(
        metric_series=dict(series),
        templates=templates,
        changes=changes,
        span_edges=edges,
        reference_ms=onset_ms - 60_000,
        data_gaps=[],
    )
    return briefing.to_dict()


def error_counts(bundle: SimBundle) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in bundle.logs:
        if str(row["level"]).upper() in {"ERROR", "FATAL", "CRIT"}:
            counts[str(row["service"])] += 1
    return dict(counts)


def run_agents(bundle: SimBundle, agents: list[str]) -> dict[str, Diagnosis]:
    truth = bundle.ground_truth
    onset_ms = bundle.base_ts_ms + int(truth.get("onset_min", 0)) * 60_000
    out: dict[str, Diagnosis] = {}
    for name in agents:
        if name == "random":
            out[name] = random_agent(SERVICES, seed=bundle.seed)
        elif name == "most_errors":
            out[name] = most_errors_agent(error_counts(bundle))
        elif name == "latest_deploy":
            out[name] = latest_deploy_agent(bundle.changes, onset_ts=onset_ms)
        elif name == "deterministic":
            out[name] = deterministic_agent(bundle_to_briefing(bundle))
        elif name == "oracle":
            out[name] = oracle_agent(truth)
        else:
            raise ValueError(f"unknown agent: {name}")
    return out


def run_suite(
    *,
    split: str = "dev",
    agents: list[str] | None = None,
    directory: Path | None = None,
) -> dict[str, Any]:
    agents = agents or ["oracle", "random", "most_errors", "latest_deploy", "deterministic"]
    scenarios = load_split(split, directory)
    per_agent: dict[str, list[Score]] = {a: [] for a in agents}
    details: list[dict[str, Any]] = []

    for sc in scenarios:
        bundle = simulate(sc)
        diags = run_agents(bundle, agents)
        row: dict[str, Any] = {"scenario": sc.id, "split": sc.split}
        for name, diag in diags.items():
            sc_score = score_diagnosis(diag, bundle.ground_truth)
            per_agent[name].append(sc_score)
            row[name] = {
                "service": diag.service,
                "abstained": diag.abstained,
                "top1": sc_score.service_top1,
            }
        details.append(row)

    return {
        "split": split,
        "agents": {a: aggregate(scores) for a, scores in per_agent.items()},
        "details": details,
        "n_scenarios": len(scenarios),
    }
