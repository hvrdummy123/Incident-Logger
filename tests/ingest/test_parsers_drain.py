from __future__ import annotations

from pathlib import Path

from traceiq.ingest.detect import detect_format
from traceiq.ingest.drain import Drain, tokenize
from traceiq.ingest.parsers.logs import group_stacktraces, parse_jsonl, parse_nginx
from traceiq.ingest.pipeline import ingest_file
from traceiq.store.query import query_logs

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "formats"


def test_jsonl_and_nginx_samples() -> None:
    line = SAMPLES.joinpath("jsonl.log").read_text(encoding="utf-8").splitlines()[1]
    ev = parse_jsonl(line)
    assert ev.parse_ok
    assert ev.service == "checkout"
    assert ev.level == "ERROR"

    nginx = SAMPLES.joinpath("nginx.log").read_text(encoding="utf-8").splitlines()[1]
    nev = parse_nginx(nginx)
    assert nev.parse_ok
    assert nev.attrs["status"] == 500


def test_detect_jsonl() -> None:
    d = detect_format(SAMPLES / "jsonl.log", seed=1)
    assert d.format == "jsonl"
    assert d.confidence > 0.5


def test_stacktrace_grouping() -> None:
    lines = SAMPLES.joinpath("plain.log").read_text(encoding="utf-8").splitlines()
    grouped = group_stacktraces(lines)
    assert any("RuntimeError: boom" in g and "Traceback" in g for g in grouped)


def test_drain_stable_and_bounded() -> None:
    d = Drain(depth=4, sim_threshold=0.5)
    ids = []
    for i in range(50):
        ids.append(d.add("checkout", f"payment failed for order {1000 + i}"))
    # Same shape → few templates, not 50
    assert len(set(ids)) <= 3
    assert all(t.startswith("tpl_") for t in ids)
    # same pattern re-ingest → same template id
    again = d.add("checkout", "payment failed for order 9999")
    assert again in ids


def test_drain_does_not_merge_different_lengths() -> None:
    d = Drain()
    a = d.add("svc", "error one two three")
    b = d.add("svc", "error one two three four five")
    assert a != b
    assert len(tokenize("error 1 2 3")) == len(tokenize("error 9 8 7"))


def test_dry_run_and_write_roundtrip(tmp_path: Path) -> None:
    result = ingest_file(SAMPLES / "jsonl.log", dry_run=True)
    assert result.report.lines_read >= 4
    assert result.report.lines_unparsed >= 1
    assert result.dataset_id is None

    wid = "ws_test_1"
    ds = "ds_test_1"
    written = ingest_file(
        SAMPLES / "jsonl.log",
        dry_run=False,
        data_dir=tmp_path,
        workspace_id=wid,
        dataset_id=ds,
        fmt="jsonl",
    )
    assert written.dataset_path is not None
    rows = query_logs(tmp_path / wid / "datasets" / ds, contains="payment", limit=10)
    assert len(rows) >= 1
    assert rows[0]["service"] == "checkout"
