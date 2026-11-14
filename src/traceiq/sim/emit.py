"""Write a SimBundle to disk in mixed log formats (for realistic ingest)."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from traceiq.sim.world import SimBundle


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def emit_bundle(bundle: SimBundle, out_dir: Path, *, mixed_formats: bool = True) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Partition logs by service for mixed formats
    by_svc: dict[str, list[dict[str, Any]]] = {}
    for row in bundle.logs:
        by_svc.setdefault(str(row["service"]), []).append(row)

    format_cycle = ["jsonl", "plain", "logfmt", "cri"]
    for i, (svc, rows) in enumerate(sorted(by_svc.items())):
        fmt = format_cycle[i % len(format_cycle)] if mixed_formats else "jsonl"
        path = out_dir / "logs" / f"{svc}.{fmt}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(_format_line(fmt, row) + "\n")

    # nginx-style for edge-lb
    edge = by_svc.get("edge-lb") or by_svc.get("gateway") or []
    if edge:
        path = out_dir / "logs" / "edge.nginx.log"
        with path.open("w", encoding="utf-8") as f:
            for row in edge[:200]:
                ts = datetime.fromtimestamp(int(row["ts"]) / 1000, tz=UTC)
                stamp = ts.strftime("%d/%b/%Y:%H:%M:%S +0000")
                status = 500 if row["level"] == "ERROR" else 200
                f.write(
                    f'10.0.0.1 - - [{stamp}] "GET / HTTP/1.1" {status} 12 "-" "sim"\n'
                )

    # metrics CSV
    metrics_path = out_dir / "metrics.csv"
    with metrics_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "name", "service", "value"])
        w.writeheader()
        for m in bundle.metrics:
            w.writerow(
                {
                    "ts": m["ts"],
                    "name": m["name"],
                    "service": m["labels"]["service"],
                    "value": m["value"],
                }
            )

    # traces OTLP-ish JSON
    (out_dir / "traces.json").write_text(
        json.dumps({"spans": bundle.spans}, indent=2), encoding="utf-8"
    )

    # changes
    with (out_dir / "changes.csv").open("w", encoding="utf-8", newline="") as f:
        fields = [
            "id",
            "ts",
            "kind",
            "service",
            "from_version",
            "to_version",
            "actor",
            "description",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in bundle.changes:
            w.writerow(
                {
                    "id": c.get("id"),
                    "ts": c.get("ts_ms"),
                    "kind": c.get("kind"),
                    "service": c.get("service"),
                    "from_version": c.get("from_version", ""),
                    "to_version": c.get("to_version", ""),
                    "actor": c.get("actor", ""),
                    "description": c.get("description", ""),
                }
            )


def _format_line(fmt: str, row: dict[str, Any]) -> str:
    ts = _iso(int(row["ts"]))
    svc = str(row["service"])
    level = str(row["level"])
    msg = str(row["message"])
    if fmt == "jsonl":
        return json.dumps(
            {
                "ts": ts,
                "service": svc,
                "level": level,
                "message": msg,
                "instance": row["instance"],
            }
        )
    if fmt == "logfmt":
        return f'ts={ts} level={level.lower()} service={svc} msg="{msg}"'
    if fmt == "cri":
        stream = "stderr" if level == "ERROR" else "stdout"
        return f"{ts} {stream} F {msg}"
    return f"{ts} {level} {svc} {msg}"
