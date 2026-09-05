"""Domain layer exports for I9 Deterministic Kill Switch / Execution Safety Control."""
from .contracts import (
    ExecutionBlockedError,
    ExecutionDecision,
    KillSwitchRecord,
    KillSwitchState,
    KillTrigger,
    RevalidationOutcome,
    RevalidationRequest,
    UnauthorizedResumeError,
)
from .policy import (
    PERMITTED_SAFETY_TRANSITIONS,
    KillSwitchPolicy,
)

__all__ = [
    "KillSwitchState",
    "KillTrigger",
    "ExecutionDecision",
    "ExecutionBlockedError",
    "UnauthorizedResumeError",
    "KillSwitchRecord",
    "RevalidationRequest",
    "RevalidationOutcome",
    "PERMITTED_SAFETY_TRANSITIONS",
    "KillSwitchPolicy",
]
