from __future__ import annotations

from datetime import UTC, datetime

from traceiq.clock import FrozenClock, ManualClock
from traceiq.config import Settings
from traceiq.ids import evidence_id, new_ulid


def test_frozen_clock_is_stable() -> None:
    t = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    clock = FrozenClock(t)
    assert clock.now() == t
    assert clock.now() == clock.now()


def test_manual_clock_advances() -> None:
    clock = ManualClock(datetime(2024, 1, 1, tzinfo=UTC))
    clock.advance_ms(1500)
    assert clock.now().timestamp() == datetime(2024, 1, 1, 0, 0, 1, 500_000, tzinfo=UTC).timestamp()


def test_ulids_are_unique_and_evidence_prefix() -> None:
    a, b = new_ulid(), new_ulid()
    assert a != b
    ev = evidence_id()
    assert ev.startswith("ev_")
    assert len(ev) > 10


def test_settings_parse_model() -> None:
    s = Settings(model="mock:mock-v1", jwt_secret="x", redaction_key="y")
    assert s.parse_model() == ("mock", "mock-v1")


def test_settings_reject_bad_provider() -> None:
    s = Settings(model="bogus:x", jwt_secret="x", redaction_key="y")
    try:
        s.parse_model()
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "unknown model provider" in str(e)
