"""Transaction Binding Service.

Manages active binding registries, attempt tracking, cross-transaction uniqueness indices,
and integrates with TransactionBindingVerifier.
"""
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Set

from backend.app.domain.binding.contracts import (
    AttemptRecord,
    AttemptStatus,
    BindingContext,
    BindingStatus,
    BindingVerificationOutcome,
    BindingViolationCode,
    PaymentBindingClaim,
)
from backend.app.domain.binding.verifier import TransactionBindingVerifier
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.payment import ProviderPayment

logger = logging.getLogger(__name__)


class DuplicateOrderBindingError(ValueError):
    """Raised when an order ID is bound to more than one transaction."""
    pass


class DuplicatePaymentBindingError(ValueError):
    """Raised when a payment ID is bound to more than one transaction."""
    pass


class AttemptLimitExceededError(ValueError):
    """Raised when a transaction exceeds its configured maximum attempt count."""
    pass


class TransactionBindingService:
    """
    Stateful runtime service managing transaction bindings, unique indices across transactions,
    and attempt lifecycles.
    """

    def __init__(self, max_attempts_per_transaction: int = 5):
        self._max_attempts = max_attempts_per_transaction
        self._contexts: Dict[str, BindingContext] = {}  # tx_id -> BindingContext
        self._order_to_tx: Dict[str, str] = {}         # order_id -> tx_id
        self._payment_to_tx: Dict[str, str] = {}       # payment_id -> tx_id
        self._attempts: Dict[str, List[AttemptRecord]] = {} # tx_id -> List[AttemptRecord]
        self._consumed_attempts: Dict[str, Set[str]] = {}   # tx_id -> Set[attempt_id]

    def register_binding(
        self,
        intent_id: str,
        agent_id: str,
        merchant_id: str,
        transaction_id: str,
        order_id: str,
        attempt_id: str = "att_1",
        created_at: Optional[datetime] = None,
    ) -> BindingContext:
        """
        Register authoritative binding context during transaction initialization.
        Enforces global order uniqueness across transactions.
        """
        now = created_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Enforce global order uniqueness
        if order_id in self._order_to_tx and self._order_to_tx[order_id] != transaction_id:
            raise DuplicateOrderBindingError(
                f"Order '{order_id}' is already bound to transaction {self._order_to_tx[order_id]}. "
                f"Cross-transaction order reuse is forbidden."
            )

        context = BindingContext(
            intent_id=intent_id,
            agent_id=agent_id,
            merchant_id=merchant_id,
            transaction_id=transaction_id,
            order_id=order_id,
            attempt_id=attempt_id,
            created_at=now,
        )

        self._contexts[transaction_id] = context
        self._order_to_tx[order_id] = transaction_id
        
        # Initialize attempt records
        initial_attempt = AttemptRecord(
            attempt_id=attempt_id,
            transaction_id=transaction_id,
            agent_id=agent_id,
            merchant_id=merchant_id,
            status=AttemptStatus.INITIATED,
            initiated_at=now,
        )
        self._attempts[transaction_id] = [initial_attempt]
        self._consumed_attempts[transaction_id] = set()

        return context

    def get_binding(self, transaction_id: str) -> Optional[BindingContext]:
        """Retrieve authoritative binding context for a transaction."""
        return self._contexts.get(transaction_id)

    def register_attempt(
        self,
        transaction_id: str,
        attempt_id: str,
        agent_id: str,
        merchant_id: str,
        now: Optional[datetime] = None,
    ) -> AttemptRecord:
        """Register a new attempt for an existing transaction, enforcing max attempt limits."""
        context = self.get_binding(transaction_id)
        if not context:
            raise KeyError(f"Transaction '{transaction_id}' has no registered binding context")

        current_attempts = self._attempts.get(transaction_id, [])
        if len(current_attempts) >= self._max_attempts:
            raise AttemptLimitExceededError(
                f"Transaction '{transaction_id}' exceeds maximum allowed attempts ({self._max_attempts})"
            )

        ts = now or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        attempt = AttemptRecord(
            attempt_id=attempt_id,
            transaction_id=transaction_id,
            agent_id=agent_id,
            merchant_id=merchant_id,
            status=AttemptStatus.INITIATED,
            initiated_at=ts,
        )
        self._attempts[transaction_id].append(attempt)
        return attempt

    def consume_attempt(
        self,
        transaction_id: str,
        attempt_id: str,
        payment_id: str,
        now: Optional[datetime] = None,
    ) -> None:
        """
        Mark an attempt as consumed by a successful payment.
        Enforces global payment uniqueness across transactions.
        """
        # Enforce global payment uniqueness
        if payment_id in self._payment_to_tx and self._payment_to_tx[payment_id] != transaction_id:
            raise DuplicatePaymentBindingError(
                f"Payment '{payment_id}' is already consumed by transaction {self._payment_to_tx[payment_id]}. "
                f"Cross-transaction payment reuse is strictly forbidden."
            )

        ts = now or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        if transaction_id not in self._consumed_attempts:
            self._consumed_attempts[transaction_id] = set()

        self._consumed_attempts[transaction_id].add(attempt_id)
        self._payment_to_tx[payment_id] = transaction_id

        # Update attempt record status
        attempts = self._attempts.get(transaction_id, [])
        updated_attempts = []
        for att in attempts:
            if att.attempt_id == attempt_id:
                updated_attempts.append(
                    AttemptRecord(
                        attempt_id=att.attempt_id,
                        transaction_id=att.transaction_id,
                        agent_id=att.agent_id,
                        merchant_id=att.merchant_id,
                        status=AttemptStatus.CONSUMED,
                        initiated_at=att.initiated_at,
                        consumed_at=ts,
                        payment_id=payment_id,
                    )
                )
            else:
                updated_attempts.append(att)
        self._attempts[transaction_id] = updated_attempts

    def verify_transaction_binding(
        self,
        claim: PaymentBindingClaim,
        authoritative_payment: Optional[ProviderPayment] = None,
        reference_time: Optional[datetime] = None,
        require_authoritative_payment: bool = False,
    ) -> BindingVerificationOutcome:
        """Verify payment claim against the transaction's authoritative context."""
        context = self.get_binding(claim.transaction_id)
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        if not context:
            return BindingVerificationOutcome(
                is_valid=False,
                status=IntegrityStatus.DRIFT,
                violations=[BindingViolationCode.TRANSACTION_MISMATCH],
                details={"transaction_id": f"No binding context found for transaction '{claim.transaction_id}'"},
                explanation=f"Transaction '{claim.transaction_id}' has no registered binding context",
                verified_at=ref_time,
            )

        # Cross-transaction payment reuse check
        if claim.payment_id in self._payment_to_tx and self._payment_to_tx[claim.payment_id] != claim.transaction_id:
            return BindingVerificationOutcome(
                is_valid=False,
                status=IntegrityStatus.DRIFT,
                violations=[BindingViolationCode.CROSS_TRANSACTION_REUSE],
                details={"payment_id": f"Payment '{claim.payment_id}' belongs to tx {self._payment_to_tx[claim.payment_id]}"},
                explanation=f"Payment '{claim.payment_id}' has already been consumed by another transaction",
                verified_at=ref_time,
            )

        consumed = self._consumed_attempts.get(claim.transaction_id, set())

        return TransactionBindingVerifier.verify(
            claim=claim,
            authoritative_context=context,
            authoritative_payment=authoritative_payment,
            consumed_attempt_ids=consumed,
            reference_time=ref_time,
            require_authoritative_payment=require_authoritative_payment,
        )
