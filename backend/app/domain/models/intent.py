"""
Intent Contract models for TarkaRaksha.
Defines what the autonomous agent was explicitly authorized to do.
Immutable once validated to prevent AI tampering or silent drift.
"""
from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .money import Money


class IntentItem(BaseModel):
    """
    Individual item authorized within an IntentContract.
    """
    item_id: str
    sku: str
    name: str
    quantity: int
    unit_price: Money
    total_price: Money

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("quantity")
    @classmethod
    def validate_positive_quantity(cls, v: int) -> int:
        if isinstance(v, bool):
            raise TypeError("Boolean value is forbidden for quantity")
        if v <= 0:
            raise ValueError("IntentItem quantity must be strictly greater than zero")
        return v

    @field_validator("total_price")
    @classmethod
    def validate_total_consistency(cls, v: Money, info) -> Money:
        unit_price = info.data.get("unit_price")
        quantity = info.data.get("quantity")
        if unit_price is not None and quantity is not None:
            expected = unit_price * quantity
            if v != expected:
                raise ValueError(
                    f"IntentItem total_price {v} does not match unit_price * quantity ({expected})"
                )
        return v


class IntentContract(BaseModel):
    """
    Immutable specification of authorized user intent.
    This is the authoritative baseline against which all observed execution is verified.
    """
    intent_id: str
    issued_by: str
    issued_at: datetime
    expires_at: datetime
    currency: str = "INR"
    max_total: Money
    items: List[IntentItem]
    allow_partial: bool = False
    allowed_substitutions: List[str] = Field(default_factory=list)
    max_successful_captures: int = 1
    max_retries: int = 3
    contract_version: str = "1.0.0"
    policy_version: str = "1.0.0"

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("issued_at", "expires_at", mode="before")
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
    def validate_expiry_after_issued(cls, v: datetime, info) -> datetime:
        issued_at = info.data.get("issued_at")
        if issued_at and v <= issued_at:
            raise ValueError("expires_at must be strictly after issued_at")
        return v

    @field_validator("max_total")
    @classmethod
    def validate_currency_alignment(cls, v: Money, info) -> Money:
        curr = info.data.get("currency")
        if curr and v.currency != curr:
            raise ValueError(f"max_total currency '{v.currency}' must match contract currency '{curr}'")
        if v.amount < 0:
            raise ValueError("max_total cannot be negative")
        return v

    @field_validator("items")
    @classmethod
    def validate_items_non_empty(cls, v: List[IntentItem]) -> List[IntentItem]:
        if not v:
            raise ValueError("IntentContract must specify at least one authorized item")
        return v

    def calculate_items_total(self) -> Money:
        """
        Calculates the sum of all item total prices.
        """
        total = Money(amount=0, currency=self.currency)
        for item in self.items:
            total = total + item.total_price
        return total
