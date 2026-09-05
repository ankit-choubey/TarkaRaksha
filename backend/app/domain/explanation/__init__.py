"""Domain package for Innovation I21 Evidence-Aware AI Explanation."""
from .contracts import (
    ClaimType,
    EvidenceReference,
    ExplanationClaim,
    ExplanationContext,
    ExplanationResult,
    ExplanationValidationResult,
    FindingCategory,
)
from .validator import validate_explanation
from .fallback import build_deterministic_fallback

__all__ = [
    "ClaimType",
    "EvidenceReference",
    "ExplanationClaim",
    "ExplanationContext",
    "ExplanationResult",
    "ExplanationValidationResult",
    "FindingCategory",
    "validate_explanation",
    "build_deterministic_fallback",
]
