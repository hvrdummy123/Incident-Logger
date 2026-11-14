"""Load scenario YAML into a typed spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from traceiq.sim.faults import FaultSpec
from traceiq.sim.groundtruth import GroundTruth


@dataclass
class Scenario:
    id: str
    seed: int
    split: str
    duration_min: int
    incident_start_min: int
    incident_end_min: int
    fault: FaultSpec
    decoys: list[str] = field(default_factory=list)
    telemetry_gaps: list[dict[str, Any]] = field(default_factory=list)
    injections: list[str] = field(default_factory=list)
    pii: bool = False
    ground_truth: GroundTruth | None = None


def load_scenario(path: Path) -> Scenario:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    fault_raw = raw["fault"]
    gt_raw = raw.get("ground_truth") or {}
    window = raw["incident_window"]
    gt = GroundTruth(
        root_cause_service=str(gt_raw.get("root_cause_service", "")),
        category=str(gt_raw.get("category", "")),
        trigger_change_id=gt_raw.get("trigger_change_id"),
        onset_min=int(gt_raw.get("onset_min", window["start_min"])),
        blast_radius=list(gt_raw.get("blast_radius") or []),
        gold_templates=list(gt_raw.get("gold_templates") or []),
        solvable=bool(gt_raw.get("solvable", True)),
    )
    return Scenario(
        id=str(raw["id"]),
        seed=int(raw["seed"]),
        split=str(raw.get("split", "train")),
        duration_min=int(raw["duration_min"]),
        incident_start_min=int(window["start_min"]),
        incident_end_min=int(window["end_min"]),
        fault=FaultSpec(
            type=str(fault_raw["type"]),
            service=str(fault_raw["service"]),
            params=dict(fault_raw.get("params") or {}),
        ),
        decoys=list(raw.get("decoys") or []),
        telemetry_gaps=list(raw.get("telemetry_gaps") or []),
        injections=list(raw.get("injections") or []),
        pii=bool(raw.get("pii", False)),
        ground_truth=gt,
    )


def list_scenarios(dir_path: Path) -> list[Path]:
    return sorted(dir_path.glob("*.yaml"))
