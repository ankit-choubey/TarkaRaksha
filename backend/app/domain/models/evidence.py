"""
Event and Evidence models for TarkaRaksha.
Provides provider-neutral representations of observations and facts with explicit source authority.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .enums import EvidenceSource
from .money import Money


class CanonicalEvent(BaseModel):
    """
    Provider-neutral representation of a transaction or execution lifecycle event.
    Shields domain models and deterministic engines from gateway-specific payload shapes.
    """
    event_id: str
    transaction_id: str
    intent_id: str
    event_type: str
    timestamp: datetime
    sequence_number: int = 1
    amount: Optional[Money] = None
    source: EvidenceSource = EvidenceSource.MERCHANT
    payload_summary: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (e.g., UTC)")
        return dt

    @field_validator("sequence_number")
    @classmethod
    def validate_sequence(cls, v: int) -> int:
        if isinstance(v, bool) or v < 1:
            raise ValueError("sequence_number must be a positive integer >= 1")
        return v


class Evidence(BaseModel):
    """
    Normalized factual evidence item extracted from observed events or authoritative gateways.
    Authority hierarchy:
    RAZORPAY (Authoritative Provider) > INTENT (Authorized User) > MERCHANT > AGENT > SYNTHETIC
    """
    evidence_id: str
    intent_id: str
    source: EvidenceSource
    field_name: str
    field_value: Any
    observed_at: datetime
    is_authoritative: bool = False
    raw_reference: Optional[str] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("observed_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware (e.g., UTC)")
        return dt

    @property
    def authority_rank(self) -> int:
        """
        Numeric authority ranking for deterministic conflict resolution.
        Higher number = higher authority.
        """
        ranks = {
            EvidenceSource.RAZORPAY: 100,
            EvidenceSource.INTENT: 90,
            EvidenceSource.MERCHANT: 70,
            EvidenceSource.REPLAY: 60,
            EvidenceSource.AGENT: 40,
            EvidenceSource.SYNTHETIC: 20,
        }
        return ranks.get(self.source, 0)
