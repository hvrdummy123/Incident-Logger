"""Read-only DuckDB queries over dataset Parquet files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


def _parquet_view(con: duckdb.DuckDBPyConnection, name: str, path: Path) -> None:
    # Paths come from our sandbox; still escape quotes for the SQL literal.
    lit = path.resolve().as_posix().replace("'", "''")
    con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{lit}')")


def connect_ro(dataset_dir: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    logs = dataset_dir / "logs.parquet"
    if logs.exists():
        _parquet_view(con, "logs", logs)
    roll = dataset_dir / "template_counts_1m.parquet"
    if roll.exists():
        _parquet_view(con, "template_counts_1m", roll)
    return con


def query_logs(
    dataset_dir: Path,
    *,
    service: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    level: str | None = None,
    contains: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 1000))
    con = connect_ro(dataset_dir)
    where = ["1=1"]
    params: list[Any] = []
    if service:
        where.append("service = ?")
        params.append(service)
    if start_ms is not None:
        where.append("ts >= ?")
        params.append(start_ms)
    if end_ms is not None:
        where.append("ts <= ?")
        params.append(end_ms)
    if level:
        where.append("level = ?")
        params.append(level)
    if contains:
        where.append("message ILIKE ?")
        params.append(f"%{contains}%")
    sql = f"SELECT * FROM logs WHERE {' AND '.join(where)} ORDER BY ts LIMIT {limit}"
    cur = con.execute(sql, params)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
