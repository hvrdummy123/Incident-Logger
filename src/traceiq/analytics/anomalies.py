"""Robust z-score (median/MAD) + CUSUM on numeric series."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True, slots=True)
class Anomaly:
    series: str
    onset_ts: int
    end_ts: int
    magnitude: float
    score: float
    method: str


def _mad(values: list[float], med: float) -> float:
    return median([abs(v - med) for v in values]) or 1e-9


def robust_z_anomalies(
    series_name: str,
    points: list[tuple[int, float]],
    *,
    pre_window: int = 30,
    z_thresh: float = 4.0,
    min_duration: int = 1,
) -> list[Anomaly]:
    """points: sorted (ts_ms, value). Baseline = first pre_window points."""
    if len(points) < pre_window + min_duration:
        return []
    base = [v for _, v in points[:pre_window]]
    med = median(base)
    mad = _mad(base, med)
    scale = 1.4826 * mad

    out: list[Anomaly] = []
    run_start: int | None = None
    run_mag = 0.0
    run_score = 0.0
    last_ts = points[pre_window][0]

    def flush(end_ts: int) -> None:
        nonlocal run_start, run_mag, run_score
        if run_start is None:
            return
        duration = sum(1 for ts, _ in points if run_start <= ts <= end_ts)
        if duration >= min_duration:
            out.append(
                Anomaly(
                    series=series_name,
                    onset_ts=run_start,
                    end_ts=end_ts,
                    magnitude=run_mag,
                    score=run_score,
                    method="robust_z",
                )
            )
        run_start = None

    for ts, v in points[pre_window:]:
        z = abs(v - med) / scale
        if z >= z_thresh:
            if run_start is None:
                run_start = ts
                run_mag = v - med
                run_score = z
            else:
                run_mag = v - med
                run_score = max(run_score, z)
        else:
            flush(last_ts)
        last_ts = ts
    flush(last_ts)
    return out


def cusum_anomalies(
    series_name: str,
    points: list[tuple[int, float]],
    *,
    pre_window: int = 30,
    drift: float = 0.5,
    threshold: float = 5.0,
) -> list[Anomaly]:
    if len(points) < pre_window + 2:
        return []
    base = [v for _, v in points[:pre_window]]
    mu = sum(base) / len(base)
    gp = gn = 0.0
    onset: int | None = None
    out: list[Anomaly] = []
    for ts, v in points[pre_window:]:
        gp = max(0.0, gp + (v - mu - drift))
        gn = max(0.0, gn - (v - mu + drift))
        if onset is None and (gp > threshold or gn > threshold):
            onset = ts
        if onset is not None and gp < 1e-9 and gn < 1e-9:
            out.append(
                Anomaly(
                    series=series_name,
                    onset_ts=onset,
                    end_ts=ts,
                    magnitude=v - mu,
                    score=max(gp, gn),
                    method="cusum",
                )
            )
            onset = None
    if onset is not None:
        out.append(
            Anomaly(
                series=series_name,
                onset_ts=onset,
                end_ts=points[-1][0],
                magnitude=points[-1][1] - mu,
                score=max(gp, gn),
                method="cusum",
            )
        )
    return out
