"""Ground truth attached to each scenario — used by evals, never by the agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GroundTruth:
    root_cause_service: str
    category: str
    trigger_change_id: str | None
    onset_min: int
    blast_radius: list[str] = field(default_factory=list)
    gold_templates: list[str] = field(default_factory=list)
    solvable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
