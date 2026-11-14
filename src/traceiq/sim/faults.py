"""Fault catalog — mutates per-minute service state during the incident window."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from traceiq.sim.topology import callers_of


@dataclass(frozen=True)
class FaultSpec:
    type: str
    service: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MinuteState:
    error_rate: float = 0.01
    latency_p95: float = 50.0
    rps: float = 100.0
    cpu: float = 0.3
    memory: float = 0.4
    pool_in_use: float = 0.2
    queue_depth: float = 0.0
    restarts: int = 0
    # (level, message, expected_lines_this_minute)
    log_templates: list[tuple[str, str, float]] = field(default_factory=list)


def root_cause_service(fault: FaultSpec) -> str:
    if fault.type == "db_pool_exhaustion" and "payments" in fault.service:
        return "payments"
    if fault.service.endswith("-db"):
        return fault.service.removesuffix("-db")
    return fault.service


def apply_fault(
    fault: FaultSpec,
    minute: int,
    onset_min: int,
    base: dict[str, MinuteState],
) -> None:
    if minute < onset_min:
        return
    svc = fault.service
    st = base.setdefault(svc, MinuteState())

    if fault.type == "bad_deploy":
        st.error_rate = 0.55
        st.latency_p95 = 220.0
        st.log_templates = [
            ("ERROR", "Unhandled exception in handler: NullPointerException", 20.0),
            ("ERROR", f"request failed after deploy of {svc}", 10.0),
        ]
        _raise_callers(base, svc, error_rate=0.18, latency=180.0)

    elif fault.type == "db_pool_exhaustion":
        st.pool_in_use = 1.0
        st.latency_p95 = 800.0
        st.error_rate = 0.3
        st.log_templates = [
            ("ERROR", "pool timeout waiting for connection", 15.0),
            ("WARN", "connection pool saturated", 5.0),
        ]
        owner = root_cause_service(fault)
        p = base.setdefault(owner, MinuteState())
        p.error_rate = 0.45
        p.latency_p95 = 650.0
        p.pool_in_use = 1.0
        p.log_templates = [
            ("ERROR", "pool timeout waiting for connection", 30.0),
            ("ERROR", "failed to checkout connection", 12.0),
        ]
        _raise_callers(base, owner, error_rate=0.22, latency=400.0)

    elif fault.type == "cache_stampede":
        st.cpu = 0.95
        st.latency_p95 = 450.0
        st.error_rate = 0.2
        st.log_templates = [
            ("WARN", "cache miss storm after flush", 40.0),
            ("ERROR", "upstream overload from cache stampede", 20.0),
        ]
        db = base.setdefault("catalog-db", MinuteState())
        db.cpu = 0.95
        db.latency_p95 = 320.0
        db.rps = 500.0
        cat = base.setdefault("catalog", MinuteState())
        cat.latency_p95 = max(cat.latency_p95, 300.0)
        cat.error_rate = max(cat.error_rate, 0.1)
        _raise_callers(base, "catalog", error_rate=0.12, latency=280.0)

    elif fault.type == "config_change":
        st.latency_p95 = 500.0
        st.error_rate = 0.25
        st.log_templates = [
            ("ERROR", "upstream request timeout after config change", 15.0),
        ]
        _raise_callers(base, svc, error_rate=0.12, latency=300.0)

    elif fault.type == "dependency_outage":
        st.error_rate = 0.9
        st.latency_p95 = 1000.0
        st.log_templates = [("ERROR", f"connection refused to {svc}", 30.0)]
        for caller in callers_of(svc):
            c = base.setdefault(caller, MinuteState())
            c.error_rate = max(c.error_rate, 0.5)
            c.log_templates = [
                ("ERROR", f"dependency {svc} unavailable — retrying", 20.0),
            ]

    elif fault.type == "feature_flag":
        st.cpu = 0.85
        st.latency_p95 = 250.0
        st.error_rate = 0.08
        st.log_templates = [
            ("INFO", "feature flag expensive_path enabled", 5.0),
            ("WARN", "slow path executed due to flag", 12.0),
        ]

    else:
        st.error_rate = 0.2
        st.cpu = 0.9
        st.log_templates = [("ERROR", f"fault {fault.type} active on {svc}", 10.0)]


def _raise_callers(
    base: dict[str, MinuteState],
    svc: str,
    *,
    error_rate: float,
    latency: float,
) -> None:
    for caller in callers_of(svc):
        c = base.setdefault(caller, MinuteState())
        c.error_rate = max(c.error_rate, error_rate)
        c.latency_p95 = max(c.latency_p95, latency)
