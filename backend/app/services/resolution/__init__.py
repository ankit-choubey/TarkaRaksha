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
from .policy import diagnose_unknown

__all__ = [
    "MAX_RESOLUTION_ATTEMPTS",
    "ResolutionCategory",
    "ResolutionStrategy",
    "ResolutionDiagnosis",
    "ResolutionResult",
    "ResolutionError",
    "InvalidResolutionStateError",
    "ResolutionExhaustedError",
    "ResolutionConflictError",
    "diagnose_unknown",
]
