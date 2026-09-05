"""
Event and Evidence models for TarkaRaksha.
Provides provider-neutral representations of observations and facts with explicit source authority.
"""
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .enums import EvidenceAuthority, EvidenceSource
from .money import Money


# Canonical mapping from source category to default authoritative weight tier
SOURCE_DEFAULT_AUTHORITY_MAP = {
    EvidenceSource.RAZORPAY: EvidenceAuthority.AUTHORITATIVE,
    EvidenceSource.INTENT: EvidenceAuthority.PROTOCOL_TRUSTED,
    EvidenceSource.USER_INTENT: EvidenceAuthority.PROTOCOL_TRUSTED,
    EvidenceSource.MERCHANT: EvidenceAuthority.MERCHANT_ATTESTED,
    EvidenceSource.REPLAY: EvidenceAuthority.REPLAY_OBSERVED,
    EvidenceSource.SYSTEM: EvidenceAuthority.SYSTEM_DERIVED,
    EvidenceSource.SYNTHETIC: EvidenceAuthority.SYSTEM_DERIVED,
    EvidenceSource.AGENT: EvidenceAuthority.ADVISORY,
}

# Numeric authority ranking for deterministic conflict resolution
AUTHORITY_RANK_MAP = {
    EvidenceAuthority.AUTHORITATIVE: 100,
    EvidenceAuthority.PROTOCOL_TRUSTED: 90,
    EvidenceAuthority.MERCHANT_ATTESTED: 70,
    EvidenceAuthority.REPLAY_OBSERVED: 60,
    EvidenceAuthority.SYSTEM_DERIVED: 50,
    EvidenceAuthority.ADVISORY: 20,
}


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
    occurred_at: Optional[datetime] = None
    sequence_number: int = 1
    amount: Optional[Money] = None
    source: EvidenceSource = EvidenceSource.MERCHANT
    authority: Optional[EvidenceAuthority] = None
    payload_summary: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("timestamp", "occurred_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
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
    Explicitly distinguishes origin source (source) from authority weighting (authority).
    """
    evidence_id: str
    intent_id: str
    transaction_id: Optional[str] = None
    source: EvidenceSource
    authority: Optional[EvidenceAuthority] = None
    field_name: str
    field_value: Any
    observed_at: datetime
    ingested_at: Optional[datetime] = None
    is_authoritative: bool = False
    raw_reference: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("observed_at", "ingested_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (e.g., UTC)")
        return dt

    @property
    def effective_authority(self) -> EvidenceAuthority:
        """Returns the explicit authority or derives the default authority from source."""
        if self.authority is not None:
            return self.authority
        return SOURCE_DEFAULT_AUTHORITY_MAP.get(self.source, EvidenceAuthority.ADVISORY)

    @property
    def authority_rank(self) -> int:
        """
        Numeric authority ranking for deterministic conflict resolution.
        Higher number = higher authority.
        """
        # If authority is explicitly provided, use its rank
        if self.authority is not None:
            return AUTHORITY_RANK_MAP.get(self.authority, 0)
        
        # Legacy/fallback source-based rank
        legacy_source_ranks = {
            EvidenceSource.RAZORPAY: 100,
            EvidenceSource.INTENT: 90,
            EvidenceSource.USER_INTENT: 90,
            EvidenceSource.MERCHANT: 70,
            EvidenceSource.REPLAY: 60,
            EvidenceSource.SYSTEM: 50,
            EvidenceSource.AGENT: 40,
            EvidenceSource.SYNTHETIC: 20,
        }
        return legacy_source_ranks.get(self.source, 0)
