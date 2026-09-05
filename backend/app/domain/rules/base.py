"""
Rule evaluation output model for TarkaRaksha.
Represents the outcome of an individual deterministic rule check (Economic, Semantic, Temporal).
"""
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from backend.app.domain.models.enums import IntegrityStatus


class RuleResult(BaseModel):
    """
    Evaluation output of a specific deterministic check.
    """
    rule_name: str
    status: IntegrityStatus
    violation: Optional[str] = None
    expected: Optional[Any] = None
    observed: Optional[Any] = None
    evidence_ids: List[str] = Field(default_factory=list)
    explanation: str = ""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @property
    def is_pass(self) -> bool:
        return self.status == IntegrityStatus.PASS

    @property
    def is_drift(self) -> bool:
        return self.status == IntegrityStatus.DRIFT

    @property
    def is_unknown(self) -> bool:
        return self.status == IntegrityStatus.UNKNOWN
