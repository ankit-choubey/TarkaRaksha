"""Deterministic Transaction Binding Verifier.

Answers: 'Does this agent/action/payment/order actually belong to the authorized transaction context?'
Zero LLM involvement. Deterministic integrity verification only.
Produces canonical Evidence records feeding TarkaRaksha's 3-way authority model.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from backend.app.domain.binding.contracts import (
    AttemptStatus,
    BindingContext,
    BindingStatus,
    BindingVerificationOutcome,
    BindingViolationCode,
    PaymentBindingClaim,
)
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.payment import ProviderPayment


class TransactionBindingVerifier:
    """
    Pure deterministic verifier that cross-examines payment claims, provider evidence,
    and authoritative binding contexts.
    """

    @classmethod
    def verify(
        cls,
        claim: PaymentBindingClaim,
        authoritative_context: BindingContext,
        authoritative_payment: Optional[ProviderPayment] = None,
        consumed_attempt_ids: Optional[Set[str]] = None,
        expected_attempt_id: Optional[str] = None,
        reference_time: Optional[datetime] = None,
        require_authoritative_payment: bool = False,
    ) -> BindingVerificationOutcome:
        """
        Verify that a payment claim matches the authoritative transaction binding context.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        violations: List[BindingViolationCode] = []
        details: Dict[str, str] = {}
        consumed = consumed_attempt_ids or set()

        # 1. Intent binding
        if claim.intent_id != authoritative_context.intent_id:
            violations.append(BindingViolationCode.INTENT_MISMATCH)
            details["intent_id"] = f"Claimed '{claim.intent_id}' != expected '{authoritative_context.intent_id}'"

        # 2. Agent binding
        if claim.agent_id != authoritative_context.agent_id:
            violations.append(BindingViolationCode.AGENT_MISMATCH)
            details["agent_id"] = f"Claimed '{claim.agent_id}' != expected '{authoritative_context.agent_id}'"

        # 3. Merchant binding
        if claim.merchant_id != authoritative_context.merchant_id:
            violations.append(BindingViolationCode.MERCHANT_MISMATCH)
            details["merchant_id"] = f"Claimed '{claim.merchant_id}' != expected '{authoritative_context.merchant_id}'"

        # 4. Transaction binding
        if claim.transaction_id != authoritative_context.transaction_id:
            violations.append(BindingViolationCode.TRANSACTION_MISMATCH)
            details["transaction_id"] = f"Claimed '{claim.transaction_id}' != expected '{authoritative_context.transaction_id}'"

        # 5. Order binding
        if claim.order_id != authoritative_context.order_id:
            violations.append(BindingViolationCode.ORDER_MISMATCH)
            details["order_id"] = f"Claimed '{claim.order_id}' != expected '{authoritative_context.order_id}'"

        # 6. Attempt binding & duplicate attempt defense
        if claim.attempt_id in consumed:
            violations.append(BindingViolationCode.DUPLICATE_ATTEMPT_REUSED)
            details["attempt_id"] = f"Attempt '{claim.attempt_id}' has already been consumed and cannot be reused"
        elif expected_attempt_id and claim.attempt_id != expected_attempt_id:
            violations.append(BindingViolationCode.ATTEMPT_MISMATCH)
            details["attempt_id"] = f"Claimed attempt '{claim.attempt_id}' != expected '{expected_attempt_id}'"

        # 7. Payment binding against authoritative provider state (if present)
        if authoritative_payment is not None:
            if authoritative_payment.payment_id != claim.payment_id:
                violations.append(BindingViolationCode.PAYMENT_MISMATCH)
                details["payment_id"] = f"Provider payment '{authoritative_payment.payment_id}' != claimed '{claim.payment_id}'"
            if authoritative_payment.order_id != authoritative_context.order_id:
                violations.append(BindingViolationCode.ORDER_MISMATCH)
                details["provider_order_id"] = f"Provider order '{authoritative_payment.order_id}' != context order '{authoritative_context.order_id}'"
        elif require_authoritative_payment:
            # When payment verification is mandatory but provider record is absent/unresolved
            return BindingVerificationOutcome(
                is_valid=False,
                status=IntegrityStatus.UNKNOWN,
                violations=[BindingViolationCode.UNRESOLVED_PROVIDER_STATE],
                details={"provider_payment": "Missing authoritative provider payment verification"},
                explanation="Authoritative payment verification unresolved: provider evidence missing",
                verified_at=ref_time,
            )

        if violations:
            violation_names = ", ".join(v.value for v in violations)
            return BindingVerificationOutcome(
                is_valid=False,
                status=IntegrityStatus.DRIFT,
                violations=violations,
                details=details,
                explanation=f"Binding verification failed: {violation_names}",
                verified_at=ref_time,
            )

        return BindingVerificationOutcome(
            is_valid=True,
            status=IntegrityStatus.PASS,
            violations=[],
            details={},
            explanation="Transaction binding verified successfully across intent, agent, merchant, order, payment, and attempt contexts.",
            verified_at=ref_time,
        )
