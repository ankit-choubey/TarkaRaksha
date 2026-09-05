"""Buyer Agent contracts for TarkaRaksha I5.

The buyer agent is a bounded decision/proposal layer. It preserves the
validated IntentContract as the authorization baseline and never authorizes
payment or integrity outcomes itself.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models import IntentContract, Money
from backend.app.domain.merchant.contracts import MerchantResponse


class BuyerAgentDecisionType(str, Enum):
    PROPOSE = "PROPOSE"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    REQUEST_MERCHANT_INFO = "REQUEST_MERCHANT_INFO"
    REPLAN = "REPLAN"
    ABSTAIN = "ABSTAIN"


class BuyerTransactionProposal(BaseModel):
    """Immutable buyer-agent proposal derived from an authorized intent."""
    proposal_id: str
    buyer_agent_id: str
    intent_id: str
    transaction_id: str
    items: List[Any] = Field(default_factory=list)
    sku: str
    quantity: int
    max_total: Money
    allowed_substitutions: List[str] = Field(default_factory=list)
    allow_partial: bool = False
    rationale: str = ""
    source: str = "buyer_agent"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            raise ValueError("quantity must be a positive integer")
        return v


class BuyerClarification(BaseModel):
    """A clarification request when the buyer goal is insufficiently specified."""
    clarification_id: str
    intent_id: Optional[str] = None
    question: str
    missing_constraint: str

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class BuyerReplanRequest(BaseModel):
    """Deterministic replan input following merchant/integrity feedback."""
    request_id: str
    buyer_agent_id: str
    intent: IntentContract
    transaction_id: str
    merchant_response: Optional[MerchantResponse] = None
    integrity_feedback: Optional[str] = None
    permitted_action: str = "REPLAN"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("transaction_id", "buyer_agent_id", "request_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("ID fields cannot be empty")
        return v



class BuyerReplanResult(BaseModel):
    """Result of a bounded buyer-agent replan; never a payment authorization."""
    result_id: str
    decision: BuyerAgentDecisionType
    proposal: Optional[BuyerTransactionProposal] = None
    clarification: Optional[BuyerClarification] = None
    reason: str

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class BuyerAgentDecision(BaseModel):
    """Structured buyer-agent output with explicit advisory authority."""
    decision: BuyerAgentDecisionType
    proposal: Optional[BuyerTransactionProposal] = None
    clarification: Optional[BuyerClarification] = None
    merchant_request: Optional[dict[str, Any]] = None
    explanation: str = ""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
