"""Ingest a file: detect → parse → report → optional parquet write."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from traceiq.ingest.detect import detect_or_override
from traceiq.ingest.drain import Drain
from traceiq.ingest.parsers.logs import iter_parsed
from traceiq.ingest.report import ParseReport, build_report
from traceiq.ingest.types import LogEvent
from traceiq.store.datasets import dataset_dir, write_manifest
from traceiq.store.writer import write_logs_parquet
from traceiq.tenancy.paths import assert_under_workspace


@dataclass
class IngestResult:
    report: ParseReport
    events: list[LogEvent]
    dataset_id: str | None = None
    dataset_path: str | None = None


def ingest_file(
    path: Path,
    *,
    fmt: str | None = None,
    dry_run: bool = True,
    data_dir: Path | None = None,
    workspace_id: str | None = None,
    dataset_id: str | None = None,
    seed: int = 0,
) -> IngestResult:
    path = path.resolve()
    detected = detect_or_override(path, fmt, seed=seed)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        events = list(
            iter_parsed(f, detected.format, source_file=path.name, group_stacks=True)
        )
    report = build_report(events, fmt=detected.format, confidence=detected.confidence)

    if dry_run:
        return IngestResult(report=report, events=events)

    if data_dir is None or workspace_id is None or dataset_id is None:
        raise ValueError("data_dir, workspace_id, and dataset_id required when not dry-run")

    ds = dataset_dir(data_dir, workspace_id, dataset_id)
    assert_under_workspace(data_dir, workspace_id, ds)
    out = ds / "logs.parquet"
    stats = write_logs_parquet(events, out, drain=Drain())
    write_manifest(
        ds,
        {
            "dataset_id": dataset_id,
            "workspace_id": workspace_id,
            "source": path.name,
            "format": detected.format,
            "parse_report": report.to_dict(),
            "stats": stats,
        },
    )
    return IngestResult(
        report=report,
        events=events,
        dataset_id=dataset_id,
        dataset_path=str(ds),
    )
