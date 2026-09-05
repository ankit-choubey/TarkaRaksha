"""Authoritative Domain Contracts for E1 — Integration Boundary.

The E1 Integration Boundary provides a single, typed application-level
transaction context that preserves explicit 7-tuple bindings:
- intent_id
- agent_id
- merchant_id
- transaction_id
- order_id
- payment_id
- attempt_id

Safety invariants:
- AI is advisory. Deterministic verification is authoritative.
- The composition layer is not an authority.
- No second integrity engine, no second payment authority, no second TIX.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.binding.contracts import BindingContext, BindingVerificationOutcome
from backend.app.domain.buyer.contracts import BuyerTransactionProposal
from backend.app.domain.merchant.contracts import MerchantResponse
from backend.app.domain.models.enums import IntegrityStatus, TransactionState
from backend.app.domain.models.evidence import CanonicalEvent, Evidence
from backend.app.domain.models.integrity import IntegrityResult, MRDP
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.money import Money
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.tix.contracts import TIXMessage


class IntegrationBoundaryStage(str, Enum):
    """Lifecycle progression stages of an orchestrated integration boundary transaction."""
    INITIALIZED = "INITIALIZED"
    INTENT_BOUND = "INTENT_BOUND"
    OFFER_RECEIVED = "OFFER_RECEIVED"
    TIX_COMMITTED = "TIX_COMMITTED"
    EVALUATED = "EVALUATED"
    PAYMENT_BOUND = "PAYMENT_BOUND"
    RECOVERED = "RECOVERED"
    RESOLVED = "RESOLVED"
    REPLAYED = "REPLAYED"
    COMPLETED = "COMPLETED"


class IntegrationTransactionContext(BaseModel):
    """Single application-level transaction context preserving explicit 7-tuple bindings."""
    transaction_id: str
    intent_id: str
    agent_id: str
    merchant_id: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    attempt_id: str = "att_1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("transaction_id", "intent_id", "agent_id", "merchant_id", "attempt_id")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("IntegrationTransactionContext identifiers cannot be empty or whitespace")
        return v.strip()

    @field_validator("created_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v

    def to_binding_context(self) -> BindingContext:
        """Converts to authoritative I8 BindingContext anchored at transaction creation."""
        if not self.order_id:
            raise ValueError("Cannot create authoritative BindingContext without order_id")
        return BindingContext(
            intent_id=self.intent_id,
            agent_id=self.agent_id,
            merchant_id=self.merchant_id,
            transaction_id=self.transaction_id,
            order_id=self.order_id,
            attempt_id=self.attempt_id,
            created_at=self.created_at,
            metadata=self.metadata,
        )

    def with_order(self, order_id: str) -> "IntegrationTransactionContext":
        """Returns a copy with bound order_id."""
        if not order_id or not order_id.strip():
            raise ValueError("order_id cannot be empty or whitespace")
        return IntegrationTransactionContext(
            transaction_id=self.transaction_id,
            intent_id=self.intent_id,
            agent_id=self.agent_id,
            merchant_id=self.merchant_id,
            order_id=order_id.strip(),
            payment_id=self.payment_id,
            attempt_id=self.attempt_id,
            created_at=self.created_at,
            metadata=self.metadata,
        )

    def with_payment(self, payment_id: str) -> "IntegrationTransactionContext":
        """Returns a copy with bound payment_id."""
        if not payment_id or not payment_id.strip():
            raise ValueError("payment_id cannot be empty or whitespace")
        return IntegrationTransactionContext(
            transaction_id=self.transaction_id,
            intent_id=self.intent_id,
            agent_id=self.agent_id,
            merchant_id=self.merchant_id,
            order_id=self.order_id,
            payment_id=payment_id.strip(),
            attempt_id=self.attempt_id,
            created_at=self.created_at,
            metadata=self.metadata,
        )


class IntegrationEvaluationResponse(BaseModel):
    """Structured response from evaluating integrity across the integration boundary."""
    transaction_id: str
    status: IntegrityStatus
    state: TransactionState
    rule_results: Dict[str, bool]
    violations: List[str]
    evidence_count: int
    mrdp: Optional[MRDP] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True, extra="forbid")


class IntegrationExecutionRecord(BaseModel):
    """Comprehensive, typed audit record of a composed transaction lifecycle."""
    context: IntegrationTransactionContext
    stage: IntegrationBoundaryStage
    intent: Optional[IntentContract] = None
    buyer_proposal: Optional[BuyerTransactionProposal] = None
    merchant_response: Optional[MerchantResponse] = None
    tix_messages: List[TIXMessage] = Field(default_factory=list)
    binding_outcome: Optional[BindingVerificationOutcome] = None
    integrity_result: Optional[IntegrityResult] = None
    order: Optional[ProviderOrder] = None
    payment: Optional[ProviderPayment] = None
    mrdp: Optional[MRDP] = None
    recovery_result: Optional[Any] = None
    replay_result: Optional[Any] = None
    history: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True, extra="forbid")
