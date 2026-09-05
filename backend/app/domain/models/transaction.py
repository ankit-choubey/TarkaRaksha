"""
Transaction domain model for TarkaRaksha.
Represents a transaction lifecycle independently of third-party SDK implementations.
"""
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .enums import TransactionState
from .money import Money


class Transaction(BaseModel):
    """
    Domain-level representation of an agentic transaction.
    """
    transaction_id: str
    intent_id: str
    state: TransactionState
    authorized_amount: Money
    captured_amount: Optional[Money] = None
    refunded_amount: Optional[Money] = None
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    event_ids: List[str] = Field(default_factory=list)
    integrity_status: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("created_at", "updated_at", mode="before")
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

    @field_validator("updated_at")
    @classmethod
    def validate_updated_after_created(cls, v: datetime, info) -> datetime:
        created_at = info.data.get("created_at")
        if created_at and v < created_at:
            raise ValueError("updated_at cannot be prior to created_at")
        return v
