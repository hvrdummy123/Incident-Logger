"""Deterministic multi-service world simulator."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from traceiq.sim.faults import MinuteState, apply_fault, root_cause_service
from traceiq.sim.noise import apply_noise, decoy_changes
from traceiq.sim.scenarios import Scenario
from traceiq.sim.topology import EDGES, SERVICES


@dataclass
class SimBundle:
    scenario_id: str
    seed: int
    base_ts_ms: int
    logs: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    spans: list[dict[str, Any]] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)
    ground_truth: dict[str, Any] = field(default_factory=dict)


def simulate(scenario: Scenario, *, base_ts_ms: int = 1_700_000_000_000) -> SimBundle:
    rng = random.Random(scenario.seed)
    gt = scenario.ground_truth.to_dict() if scenario.ground_truth else {}
    bundle = SimBundle(
        scenario_id=scenario.id,
        seed=scenario.seed,
        base_ts_ms=base_ts_ms,
        ground_truth=gt,
    )

    onset = int(gt.get("onset_min", scenario.incident_start_min))
    missing_log_services = {
        str(g["service"])
        for g in scenario.telemetry_gaps
        if g.get("logs") in (True, "missing")
    }

    if scenario.fault.type in {"bad_deploy", "config_change", "feature_flag"}:
        trigger_id = gt.get("trigger_change_id") or f"chg_trigger_{scenario.seed}"
        trigger_svc = (
            root_cause_service(scenario.fault)
            if scenario.fault.type != "bad_deploy"
            else scenario.fault.service
        )
        kind = "deploy" if scenario.fault.type == "bad_deploy" else scenario.fault.type
        bundle.changes.append(
            {
                "id": trigger_id,
                "ts_ms": base_ts_ms + (onset - 2) * 60_000,
                "kind": kind,
                "service": trigger_svc,
                "from_version": "1.0.0",
                "to_version": "1.1.0",
                "actor": "ci",
                "description": f"{scenario.fault.type} trigger",
            }
        )
        bundle.ground_truth["trigger_change_id"] = trigger_id

    bundle.changes.extend(
        decoy_changes(
            rng,
            decoys=scenario.decoys,
            onset_min=onset,
            base_ts_ms=base_ts_ms,
        )
    )

    for minute in range(scenario.duration_min):
        ts = base_ts_ms + minute * 60_000
        states: dict[str, MinuteState] = {s: MinuteState() for s in SERVICES}
        apply_noise(rng, minute, states, decoys=scenario.decoys)
        if scenario.incident_start_min <= minute <= scenario.incident_end_min:
            apply_fault(scenario.fault, minute, onset, states)

        for svc, st in states.items():
            for metric, value in (
                ("error_rate", st.error_rate),
                ("latency_p95", st.latency_p95),
                ("rps", st.rps),
                ("cpu", st.cpu),
                ("memory", st.memory),
                ("pool_in_use", st.pool_in_use),
                ("queue_depth", st.queue_depth),
            ):
                bundle.metrics.append(
                    {
                        "ts": ts,
                        "name": metric,
                        "labels": {"service": svc},
                        "value": float(value),
                    }
                )

            if svc in missing_log_services:
                continue

            templates = list(st.log_templates) or [
                ("INFO", f"{svc} handled request", max(1.0, st.rps / 50.0)),
            ]
            if st.error_rate > 0.05 and not st.log_templates:
                templates.append(("ERROR", f"{svc} request failed", st.error_rate * 10))

            for level, msg, rate in templates:
                n = max(0, int(rate + rng.random()))
                for i in range(n):
                    bundle.logs.append(
                        {
                            "ts": ts + i * 10,
                            "service": svc,
                            "instance": f"{svc}-0",
                            "level": level,
                            "message": msg,
                        }
                    )

            for dst in EDGES.get(svc, []):
                if rng.random() > 0.05:
                    continue
                peer = states.get(dst, MinuteState())
                err = rng.random() < max(st.error_rate, peer.error_rate)
                bundle.spans.append(
                    {
                        "trace_id": f"tr_{scenario.seed}_{minute}_{svc}_{dst}",
                        "span_id": f"sp_{rng.randint(1, 1_000_000)}",
                        "parent_id": "",
                        "service": svc,
                        "name": f"call {dst}",
                        "start_ts": ts,
                        "duration_ms": int(st.latency_p95 * (2 if err else 1)),
                        "status": "ERROR" if err else "OK",
                        "attrs": {"peer.service": dst},
                    }
                )

    for line in scenario.injections:
        bundle.logs.append(
            {
                "ts": base_ts_ms + onset * 60_000,
                "service": "gateway",
                "instance": "gateway-0",
                "level": "INFO",
                "message": line,
            }
        )

    return bundle


def write_bundle(bundle: SimBundle, out_dir: Path, *, mixed_formats: bool = True) -> None:
    from traceiq.sim.emit import emit_bundle

    emit_bundle(bundle, out_dir, mixed_formats=mixed_formats)
    (out_dir / "ground_truth.json").write_text(
        json.dumps(bundle.ground_truth, indent=2), encoding="utf-8"
    )
