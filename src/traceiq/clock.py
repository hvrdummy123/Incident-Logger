"""Injectable clock so simulators, parsers, and evals stay deterministic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Fixed instant — pass into anything that must not call wall-clock time."""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        self._instant = instant

    def now(self) -> datetime:
        return self._instant


class ManualClock:
    """Advanceable clock for tests and the simulator."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance_ms(self, ms: int) -> datetime:
        from datetime import timedelta

        self._now = self._now + timedelta(milliseconds=ms)
        return self._now
