"""Investigation state machine statuses."""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    QUEUED = "QUEUED"
    SCOPING = "SCOPING"
    BRIEFING = "BRIEFING"
    INVESTIGATING = "INVESTIGATING"
    VERIFYING = "VERIFYING"
    REPORTING = "REPORTING"
    DONE = "DONE"
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TRANSITIONS: dict[Status, set[Status]] = {
    Status.QUEUED: {Status.SCOPING, Status.CANCELLED},
    Status.SCOPING: {Status.BRIEFING, Status.FAILED, Status.CANCELLED},
    Status.BRIEFING: {Status.INVESTIGATING, Status.REPORTING, Status.FAILED, Status.CANCELLED},
    Status.INVESTIGATING: {
        Status.VERIFYING,
        Status.REPORTING,
        Status.ABSTAINED,
        Status.FAILED,
        Status.CANCELLED,
    },
    Status.VERIFYING: {Status.REPORTING, Status.ABSTAINED, Status.FAILED},
    Status.REPORTING: {Status.DONE, Status.ABSTAINED, Status.FAILED},
}


def can_transition(src: Status, dst: Status) -> bool:
    return dst in TRANSITIONS.get(src, set())
