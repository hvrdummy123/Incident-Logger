"""Report schema (pydantic) for agent output."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Symptom(BaseModel):
    text: str
    evidence: list[str] = Field(default_factory=list)


class Impact(BaseModel):
    services: list[str] = Field(default_factory=list)
    start: str = ""
    end: str = ""
    symptoms: list[Symptom] = Field(default_factory=list)


class TimelineItem(BaseModel):
    ts: str
    text: str
    evidence: list[str] = Field(default_factory=list)


class RootCause(BaseModel):
    service: str = ""
    category: str = ""
    trigger_change_id: str | None = None
    explanation: str = ""
    evidence: list[str] = Field(default_factory=list)


class Factor(BaseModel):
    text: str
    evidence: list[str] = Field(default_factory=list)


class RuledOut(BaseModel):
    hypothesis: str
    why: str
    evidence: list[str] = Field(default_factory=list)


class Action(BaseModel):
    text: str
    type: Literal["mitigation", "follow_up"] = "follow_up"
    risk: Literal["low", "medium", "high"] = "low"


class RunMeta(BaseModel):
    model: str = ""
    prompt_version: str = ""
    steps: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    deterministic_only: bool = False


class SuspectScore(BaseModel):
    service: str
    score: float


class SeriesPoint(BaseModel):
    ts_ms: int
    value: float


class ErrorSeries(BaseModel):
    service: str
    points: list[SeriesPoint] = Field(default_factory=list)


class TimelineMark(BaseModel):
    ts_ms: int
    label: str
    kind: Literal["onset", "change", "error"] = "change"


class ReportViz(BaseModel):
    """Chart-ready payload for interactive report UI."""

    suspect_scores: list[SuspectScore] = Field(default_factory=list)
    error_series: list[ErrorSeries] = Field(default_factory=list)
    timeline_marks: list[TimelineMark] = Field(default_factory=list)
    confidence: float = 0.0


class Report(BaseModel):
    summary: str
    outcome: Literal["root_cause_found", "abstained"]
    confidence: float = 0.0
    impact: Impact = Field(default_factory=Impact)
    timeline: list[TimelineItem] = Field(default_factory=list)
    root_cause: RootCause = Field(default_factory=RootCause)
    contributing_factors: list[Factor] = Field(default_factory=list)
    ruled_out: list[RuledOut] = Field(default_factory=list)
    suggested_actions: list[Action] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    viz: ReportViz = Field(default_factory=ReportViz)
    run: RunMeta = Field(default_factory=RunMeta)


def parse_report(data: dict[str, Any] | Report) -> Report:
    if isinstance(data, Report):
        return data
    return Report.model_validate(data)
