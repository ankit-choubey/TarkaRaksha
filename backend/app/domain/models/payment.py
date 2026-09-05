"""
Provider-Neutral Payment Domain Models for TarkaRaksha.
Defines clean representations of orders, payments, and webhook events
without leaking provider-specific schema details into domain business logic.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .money import Money


class ProviderOrder(BaseModel):
    """
    Provider-neutral representation of a payment gateway order.
    Amount is strictly maintained in integer minor units (Money).
    """
    order_id: str = Field(..., description="Gateway unique order identifier (e.g., order_XYZ)")
    amount: Money = Field(..., description="Order total in integer minor currency units")
    currency: str = Field(default="INR", description="ISO-4217 three-letter currency code")
    receipt: Optional[str] = Field(default=None, description="Internal receipt or intent tracking reference")
    status: str = Field(default="created", description="Order status reported by gateway (created, attempted, paid)")
    created_at: datetime = Field(..., description="Timestamp of order creation (timezone-aware UTC)")
    notes: Dict[str, str] = Field(default_factory=dict, description="Metadata notes attached to the order")
    raw_reference: Optional[str] = Field(default=None, description="Opaque reference identifier from provider")

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")

        if dt.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (e.g., UTC)")
        return dt

    @field_validator("amount")
    @classmethod
    def validate_currency_alignment(cls, v: Money, info) -> Money:
        curr = info.data.get("currency")
        if curr and v.currency != curr:
            raise ValueError(f"Order amount currency '{v.currency}' does not match order currency '{curr}'")
        return v


class ProviderPayment(BaseModel):
    """
    Provider-neutral representation of an individual payment attempt/transaction.
    """
    payment_id: str = Field(..., description="Gateway unique payment identifier (e.g., pay_XYZ)")
    order_id: Optional[str] = Field(default=None, description="Associated gateway order identifier")
    amount: Money = Field(..., description="Payment amount in integer minor currency units")
    currency: str = Field(default="INR", description="ISO-4217 three-letter currency code")
    status: str = Field(..., description="Gateway payment status (e.g., captured, authorized, failed, refunded)")
    method: Optional[str] = Field(default=None, description="Payment instrument method (e.g., upi, card, netbanking)")
    captured: bool = Field(default=False, description="Whether the funds have been captured by merchant")
    created_at: datetime = Field(..., description="Timestamp of payment creation (timezone-aware UTC)")
    error_code: Optional[str] = Field(default=None, description="Gateway error code if failed")
    error_description: Optional[str] = Field(default=None, description="Gateway human-readable error description")
    notes: Dict[str, str] = Field(default_factory=dict, description="Metadata notes attached to payment")

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")

        if dt.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (e.g., UTC)")
        return dt

    @field_validator("amount")
    @classmethod
    def validate_currency_alignment(cls, v: Money, info) -> Money:
        curr = info.data.get("currency")
        if curr and v.currency != curr:
            raise ValueError(f"Payment amount currency '{v.currency}' does not match payment currency '{curr}'")
        return v


class ProviderWebhookEvent(BaseModel):
    """
    Provider-neutral representation of a validated incoming gateway webhook notification.
    """
    event_id: str = Field(..., description="Unique gateway event delivery identifier")
    event_type: str = Field(..., description="Canonical gateway event name (e.g., payment.captured, order.paid)")
    payment: Optional[ProviderPayment] = Field(default=None, description="Parsed payment entity if present in event")
    order: Optional[ProviderOrder] = Field(default=None, description="Parsed order entity if present in event")
    created_at: datetime = Field(..., description="Gateway event generation timestamp (UTC)")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Untrusted raw payload preserved for audit trail")

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"Timestamp must be datetime or ISO string, got {type(v).__name__}")

        if dt.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (e.g., UTC)")
        return dt
