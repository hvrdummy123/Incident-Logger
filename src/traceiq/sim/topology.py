"""Fixed 16-node shop topology for the simulator."""

from __future__ import annotations

# caller -> callees
EDGES: dict[str, list[str]] = {
    "edge-lb": ["gateway"],
    "gateway": ["auth", "catalog", "cart", "checkout", "search", "recs"],
    "cart": ["catalog", "redis-cache"],
    "catalog": ["catalog-db", "redis-cache"],
    "checkout": ["cart", "payments", "inventory", "notifications"],
    "payments": ["payments-db", "psp-external"],
    "inventory": ["inventory-db"],
    "search": ["search-index"],
    "recs": ["feature-store"],
    "notifications": ["queue"],
    "queue": ["email-worker"],
}

SERVICES = sorted({n for src, dsts in EDGES.items() for n in [src, *dsts]})


def callers_of(service: str) -> list[str]:
    return [src for src, dsts in EDGES.items() if service in dsts]


def downstream(service: str) -> list[str]:
    return list(EDGES.get(service, []))
