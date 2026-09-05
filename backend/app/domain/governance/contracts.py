"""
Governance and Policy Versioning Contracts for TarkaRaksha (I3.1).

Defines:
- GovernanceVersion / PolicyVersion attribution contracts
- Invariants ensuring every deterministic decision is attributable to rules_version and policy_version.
- Pure immutable data structures with validation.
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_RULES_VERSION: str = "integrity-1.0.0"
DEFAULT_POLICY_VERSION: str = "merchant-policy-1.0.0"


class GovernanceVersion(BaseModel):
    """
    Explicit version context attributing deterministic decision rules and policy governance.
    Enforces that versions are explicit strings and never empty/whitespace.
    """
    rules_version: str = Field(default=DEFAULT_RULES_VERSION, description="Authoritative integrity rules version (e.g. 'integrity-1.0')")
    policy_version: str = Field(default=DEFAULT_POLICY_VERSION, description="Authoritative business/merchant policy version (e.g. 'merchant-policy-3')")
    description: Optional[str] = Field(default=None, description="Optional human-readable governance rationale or changelog summary")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Deterministic policy parameters / thresholds locked to this version")

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("rules_version", "policy_version")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Governance version string cannot be empty or whitespace.")
        return v.strip()
