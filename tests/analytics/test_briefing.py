from __future__ import annotations

from traceiq.analytics.anomalies import cusum_anomalies, robust_z_anomalies
from traceiq.analytics.briefing import build_briefing
from traceiq.analytics.changes import ChangeEvent
from traceiq.analytics.compare import compare_windows
from traceiq.analytics.suspects import rank_suspects


def _step_series(onset_idx: int = 40) -> list[tuple[int, float]]:
    pts = []
    for i in range(80):
        v = 1.0 if i < onset_idx else 10.0
        pts.append((1_700_000_000_000 + i * 60_000, v))
    return pts


def test_robust_z_finds_step() -> None:
    pts = _step_series(40)
    anoms = robust_z_anomalies("payments.error_rate", pts, pre_window=30, z_thresh=3.0)
    assert anoms
    assert anoms[0].onset_ts == pts[40][0]


def test_cusum_finds_sustained_shift() -> None:
    pts = _step_series(40)
    anoms = cusum_anomalies("payments.error_rate", pts, pre_window=30)
    assert anoms
    assert anoms[0].onset_ts <= pts[45][0]


def test_compare_windows_ranks_jump() -> None:
    before = [{"template_id": "a", "count": 10}, {"template_id": "b", "count": 10}]
    during = [{"template_id": "a", "count": 10}, {"template_id": "b", "count": 100}]
    diffs = compare_windows(before, during, before_minutes=10, during_minutes=10)
    assert diffs[0].key == "b"
    assert diffs[0].delta > 0


def test_briefing_ranks_deployed_service() -> None:
    pts = _step_series(40)
    # name encodes service for suspect ranking
    series = {"payments.error_rate": pts, "checkout.error_rate": [(t, 1.0) for t, _ in pts]}
    changes = [
        ChangeEvent(
            id="chg1",
            ts_ms=pts[38][0],
            kind="deploy",
            service="payments",
            description="v42",
        )
    ]
    templates = [
        {
            "template_id": "tpl_x",
            "service": "payments",
            "pattern": "connection pool timeout <*>",
            "first_seen": pts[40][0],
            "count_after": 40,
            "count_before": 0,
        }
    ]
    edges = [("checkout", "payments", True)] * 5 + [("gateway", "checkout", True)] * 3
    briefing = build_briefing(
        metric_series=series,
        templates=templates,
        changes=changes,
        span_edges=edges,
        reference_ms=pts[39][0],
        data_gaps=["inventory logs missing"],
    )
    assert briefing.suspects
    assert briefing.suspects[0].service == "payments"
    assert briefing.data_gaps == ["inventory logs missing"]
    assert briefing.confidence > 0
    # contributions are explainable
    kinds = {c.kind for c in briefing.suspects[0].contributions}
    assert "anomaly" in kinds or "change" in kinds or "new_template" in kinds


def test_decoy_deploy_does_not_outrank_true_cause_alone() -> None:
    """Naive 'latest deploy' would pick cart; ranking should prefer payments signals."""
    pts = _step_series(40)
    changes = [
        ChangeEvent(
            id="decoy",
            ts_ms=pts[39][0],
            kind="deploy",
            service="cart",
            description="decoy",
        ),
        ChangeEvent(
            id="real",
            ts_ms=pts[35][0],
            kind="deploy",
            service="payments",
            description="real",
        ),
    ]
    from traceiq.analytics.anomalies import Anomaly
    from traceiq.analytics.changes import correlate_changes
    from traceiq.analytics.newtemplates import NewTemplate

    anoms = [
        Anomaly("payments.error_rate", pts[40][0], pts[50][0], 9.0, 8.0, "robust_z")
    ]
    hits = correlate_changes(pts[40][0], "payments", changes)
    nts = [
        NewTemplate("tpl", "payments", "pool timeout", pts[40][0], 20, 20.0)
    ]
    ranked = rank_suspects(anomalies=anoms, changes=hits, new_templates=nts)
    assert ranked[0].service == "payments"
