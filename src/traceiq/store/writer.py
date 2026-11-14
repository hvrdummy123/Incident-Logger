"""Stream LogEvents to Parquet + template rollups."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from traceiq.ingest.drain import Drain
from traceiq.ingest.types import LogEvent

LOG_SCHEMA = pa.schema(
    [
        ("ts", pa.int64()),
        ("service", pa.string()),
        ("instance", pa.string()),
        ("level", pa.string()),
        ("message", pa.string()),
        ("template_id", pa.string()),
        ("trace_id", pa.string()),
        ("span_id", pa.string()),
        ("attrs", pa.string()),
        ("source_file", pa.string()),
        ("line_no", pa.int32()),
    ]
)


def write_logs_parquet(
    events: list[LogEvent],
    out_path: Path,
    *,
    drain: Drain | None = None,
    row_group_size: int = 50_000,
) -> dict[str, Any]:
    drain = drain or Drain()
    cols: dict[str, list[Any]] = {f.name: [] for f in LOG_SCHEMA}
    rollup: dict[tuple[str, str, str, int], int] = defaultdict(int)

    for ev in events:
        tid = drain.add(ev.service, ev.message) if ev.parse_ok else ""
        ev.template_id = tid
        cols["ts"].append(ev.ts_ms if ev.ts_ms is not None else 0)
        cols["service"].append(ev.service)
        cols["instance"].append(ev.instance)
        cols["level"].append(ev.level)
        cols["message"].append(ev.message)
        cols["template_id"].append(tid)
        cols["trace_id"].append(ev.trace_id)
        cols["span_id"].append(ev.span_id)
        cols["attrs"].append(json.dumps(ev.attrs, default=str))
        cols["source_file"].append(ev.source_file)
        cols["line_no"].append(ev.line_no)
        if ev.ts_ms is not None and tid:
            minute = (ev.ts_ms // 60_000) * 60_000
            rollup[(ev.service, tid, ev.level, minute)] += 1

    table = pa.Table.from_pydict(cols, schema=LOG_SCHEMA)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out_path, row_group_size=row_group_size)

    # rollups as a second parquet beside logs
    r_cols: dict[str, list[Any]] = {
        "service": [],
        "template_id": [],
        "level": [],
        "minute": [],
        "count": [],
    }
    for (svc, tid, level, minute), count in sorted(rollup.items()):
        r_cols["service"].append(svc)
        r_cols["template_id"].append(tid)
        r_cols["level"].append(level)
        r_cols["minute"].append(minute)
        r_cols["count"].append(count)
    roll_path = out_path.with_name("template_counts_1m.parquet")
    pq.write_table(pa.Table.from_pydict(r_cols), roll_path)

    templates = [
        {
            "template_id": t.template_id,
            "service": t.service,
            "pattern": t.pattern,
            "example_message": t.example_message,
            "count": t.count,
        }
        for t in drain.templates()
    ]
    (out_path.parent / "templates.json").write_text(
        json.dumps(templates, indent=2), encoding="utf-8"
    )
    return {"rows": len(events), "templates": len(templates), "path": str(out_path)}
