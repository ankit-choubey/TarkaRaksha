"""
UNKNOWN Resolution subsystem for TarkaRaksha (T12).
Exports contracts, diagnostic policy, observation engine, and orchestrator.
"""
from .contracts import (
    MAX_RESOLUTION_ATTEMPTS,
    InvalidResolutionStateError,
    ResolutionCategory,
    ResolutionConflictError,
    ResolutionDiagnosis,
    ResolutionError,
    ResolutionExhaustedError,
    ResolutionResult,
    ResolutionStrategy,
)
from .observer import LEGAL_RESOLUTION_STATES, UnknownObserver
from .policy import diagnose_unknown

__all__ = [
    "MAX_RESOLUTION_ATTEMPTS",
    "LEGAL_RESOLUTION_STATES",
    "ResolutionCategory",
    "ResolutionStrategy",
    "ResolutionDiagnosis",
    "ResolutionResult",
    "ResolutionError",
    "InvalidResolutionStateError",
    "ResolutionExhaustedError",
    "ResolutionConflictError",
    "diagnose_unknown",
    "UnknownObserver",
]

