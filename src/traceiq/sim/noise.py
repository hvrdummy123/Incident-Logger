"""Benign noise and decoys so heuristics can fail honestly."""

from __future__ import annotations

import random

from traceiq.sim.faults import MinuteState
from traceiq.sim.topology import SERVICES


def apply_noise(
    rng: random.Random,
    minute: int,
    base: dict[str, MinuteState],
    *,
    decoys: list[str],
) -> list[dict[str, object]]:
    """Return extra change events (decoys) for this minute; mutate base lightly."""
    changes: list[dict[str, object]] = []

    # baseline chatter
    for svc in SERVICES:
        st = base.setdefault(svc, MinuteState())
        st.error_rate = max(0.0, st.error_rate + rng.uniform(-0.002, 0.002))
        st.rps = max(1.0, st.rps * (0.95 + rng.random() * 0.1))
        if rng.random() < 0.02:
            st.log_templates = list(st.log_templates) + [
                ("INFO", "health check ok", 2.0),
            ]

    # hourly batch spike
    if "hourly_batch_spike" in decoys and minute % 60 == 0:
        inv = base.setdefault("inventory", MinuteState())
        inv.rps *= 3
        inv.cpu = min(1.0, inv.cpu + 0.3)
        inv.log_templates = list(inv.log_templates) + [
            ("INFO", "hourly inventory reconciliation started", 5.0),
        ]

    return changes


def decoy_changes(
    rng: random.Random,
    *,
    decoys: list[str],
    onset_min: int,
    base_ts_ms: int,
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    if "unrelated_deploy" in decoys:
        out.append(
            {
                "id": f"chg_unrelated_{rng.randint(1000, 9999)}",
                "ts_ms": base_ts_ms + (onset_min + 5) * 60_000,
                "kind": "deploy",
                "service": "recs",
                "from_version": "1.0.0",
                "to_version": "1.0.1",
                "actor": "ci",
                "description": "unrelated recs deploy during incident",
            }
        )
    if "innocent_deploy_before_onset" in decoys:
        out.append(
            {
                "id": f"chg_innocent_{rng.randint(1000, 9999)}",
                "ts_ms": base_ts_ms + (onset_min - 4) * 60_000,
                "kind": "deploy",
                "service": "cart",
                "from_version": "3.2.0",
                "to_version": "3.2.1",
                "actor": "ci",
                "description": "innocent cart deploy before onset",
            }
        )
    return out
