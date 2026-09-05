"""
Authorization domain model for TarkaRaksha.
Represents explicit approval granting bounded transaction authority to an autonomous agent.
Distinct from AI confidence, agent recommendations, or payment results.
"""
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .money import Money


class Authorization(BaseModel):
    """
    Formal grant of authority for an autonomous agent to execute within prescribed boundaries.
    """
    authorization_id: str
    intent_id: str
    authorizer_id: str
    authorized_at: datetime
    expires_at: datetime
    authorized_amount: Money
    authorized_actions: List[str] = Field(default_factory=lambda: ["PAYMENT_CAPTURE"])
    merchant_id: Optional[str] = None
    policy_hash: Optional[str] = None
    signature: Optional[str] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("authorized_at", "expires_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")
        
        if dt.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware (e.g., UTC)")
        return dt

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, v: datetime, info) -> datetime:
        authorized_at = info.data.get("authorized_at")
        if authorized_at and v <= authorized_at:
            raise ValueError("expires_at must be strictly after authorized_at")
        return v

    def is_expired(self, current_time: datetime) -> bool:
        """
        Check if authorization is expired at the given timezone-aware time.
        """
        if current_time.tzinfo is None:
            raise ValueError("current_time must be timezone-aware")
        return current_time > self.expires_at
