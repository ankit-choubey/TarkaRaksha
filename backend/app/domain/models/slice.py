"""
Data Transfer Objects and Schemas for TarkaRaksha Transaction Slice (T10).
Defines request and response schemas for order creation, checkout completion,
and verification outcomes across the API and service boundary.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import IntegrityStatus, TransactionState
from .intent import IntentContract
from .integrity import MRDP
from .money import Money


class CreateTransactionRequest(BaseModel):
    """
    Request payload to initiate a protected transaction slice.
    May supply a structured IntentContract or natural language intent string.
    """
    intent: Optional[IntentContract] = None
    natural_language_intent: Optional[str] = None
    issued_by: str = "user_default"

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("natural_language_intent")
    @classmethod
    def validate_content_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("natural_language_intent cannot be empty or whitespace")
        return v


class CreateTransactionResponse(BaseModel):
    """
    Response returned to client upon successful order creation.
    Exposes only public gateway checkout parameters. Never exposes secrets.
    """
    transaction_id: str
    intent_id: str
    order_id: str
    amount: Money
    currency: str
    state: TransactionState
    key_id: Optional[str] = None  # Razorpay public key ID for frontend checkout popup
    created_at: datetime

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class CompleteTransactionRequest(BaseModel):
    """
    Request payload submitted by client upon checkout completion.
    Contains gateway receipt parameters requiring server-side verification.
    """
    transaction_id: str
    order_id: str
    payment_id: str
    signature: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("transaction_id", "order_id", "payment_id", "signature")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()


class CompleteTransactionResponse(BaseModel):
    """
    Authoritative response from TarkaRaksha control plane evaluating transaction integrity.
    """
    transaction_id: str
    intent_id: str
    order_id: str
    payment_id: str
    state: TransactionState
    integrity_status: IntegrityStatus
    rule_results: Dict[str, bool] = Field(default_factory=dict)
    violations: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    mrdp: Optional[MRDP] = None
    verified_at: datetime

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class RecoverTransactionRequest(BaseModel):
    """
    Request payload submitted to trigger the recovery loop for a drifted or unresolved transaction.
    """
    transaction_id: str
    action_request: Optional[Any] = None  # ActionRequest
    use_ai: bool = False

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("transaction_id")
    @classmethod
    def validate_transaction_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("transaction_id cannot be empty or whitespace")
        return v.strip()
