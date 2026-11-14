"""Per-investigation budgets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Budget:
    max_steps: int = 25
    max_tokens: int = 100_000
    max_cost_usd: float = 0.50
    wall_clock_s: float = 180.0
    steps: int = 0
    tokens: int = 0
    cost_usd: float = 0.0

    def record(self, *, tokens: int = 0, cost: float = 0.0) -> None:
        self.steps += 1
        self.tokens += tokens
        self.cost_usd += cost

    def exhausted(self) -> str | None:
        if self.steps >= self.max_steps:
            return "max_steps"
        if self.tokens >= self.max_tokens:
            return "max_tokens"
        if self.cost_usd >= self.max_cost_usd:
            return "max_cost"
        return None
