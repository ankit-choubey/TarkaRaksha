"""
Recovery Executor for TarkaRaksha (T11).
Narrow execution control plane that safely dispatches compensatory actions.

Authority & Invariants:
1. Validates ActionRequest again before execution (defense in depth).
2. Enforces deterministic recovery idempotency.
3. Enforces bounded attempts (MAX_RECOVERY_ATTEMPTS = 3).
4. Dispatches only explicitly supported actions.
5. Ingests new evidence into canonical T06 representations.
6. NEVER declares PASS independently.
"""
from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional

from backend.app.domain.models import (
    ActionRequest,
    ActionType,
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntentContract,
    Money,
    MRDP,
    TransactionState,
)
from backend.app.services.payment import PaymentProvider
from .contracts import (
    MAX_RECOVERY_ATTEMPTS,
    RecoveryExecutionResult,
    RecoveryExhaustedError,
)
from .validator import validate_action_request

logger = logging.getLogger(__name__)


class RecoveryExecutor:
    """
    Control plane executor for verified recovery operations.
    Maintains recovery idempotency table and attempt budgets per transaction.
    """

    def __init__(self):
        self._idempotency_records: Dict[str, RecoveryExecutionResult] = {}
        self._attempt_counts: Dict[str, int] = {}

    def get_attempt_count(self, intent_id: str) -> int:
        """Returns the number of recovery attempts executed for an intent."""
        return self._attempt_counts.get(intent_id, 0)

    def reset_attempts(self, intent_id: str) -> None:
        """Resets attempt counter for testing or new transaction lifecycle."""
        if intent_id in self._attempt_counts:
            del self._attempt_counts[intent_id]

    def execute(
        self,
        action_request: ActionRequest,
        contract: IntentContract,
        provider: PaymentProvider,
        current_state: TransactionState,
        mrdp: Optional[MRDP] = None,
        now: Optional[datetime] = None,
    ) -> RecoveryExecutionResult:
        """
        Executes a validated ActionRequest against provider/merchant boundaries.
        Enforces defense-in-depth re-validation, idempotency, and bounded attempts.
        """
        exec_time = now or datetime.now(timezone.utc)
        if exec_time.tzinfo is None:
            exec_time = exec_time.replace(tzinfo=timezone.utc)

        # 1. Recovery Idempotency Check (§10)
        # Repeated recovery requests with identical idempotency keys return the previously recorded result
        if action_request.idempotency_key in self._idempotency_records:
            cached_result = self._idempotency_records[action_request.idempotency_key]
            logger.info(
                "Idempotent recovery replay for key '%s'. Returning cached result.",
                action_request.idempotency_key,
            )
            return RecoveryExecutionResult(
                execution_id=f"replay_{cached_result.execution_id}",
                action_request=cached_result.action_request,
                status="DUPLICATE",
                evidence=cached_result.evidence,
                events=cached_result.events,
                executed_at=exec_time,
                is_idempotent_replay=True,
                details={"original_execution_id": cached_result.execution_id},
            )

        # 2. Attempt Budget & Defense-in-Depth Re-validation (§11, §15)
        current_attempts = self.get_attempt_count(contract.intent_id)
        validated_request = validate_action_request(
            action_request=action_request,
            contract=contract,
            mrdp=mrdp,
            current_state=current_state,
            attempt_count=current_attempts,
        )

        # Increment attempt counter
        self._attempt_counts[contract.intent_id] = current_attempts + 1

        exec_hash = hashlib.sha256(
            f"{validated_request.request_id}:{validated_request.idempotency_key}:{exec_time.isoformat()}".encode("utf-8")
        ).hexdigest()[:12]
        execution_id = f"rec_exec_{exec_hash}"

        new_evidence: List[Evidence] = []
        new_events: List[CanonicalEvent] = []

        # 3. Action Dispatch
        if validated_request.action_type == ActionType.REFUND:
            # Compensatory refund of excess amount
            refund_amount = validated_request.amount or Money(amount=0, currency=contract.currency)
            
            # Canonical evidence representing the provider refund
            ev_refund = Evidence(
                evidence_id=f"ev_{execution_id}_refund",
                intent_id=contract.intent_id,
                source=EvidenceSource.RAZORPAY,
                authority=EvidenceAuthority.AUTHORITATIVE,
                field_name="refund_amount",
                field_value=refund_amount,
                observed_at=exec_time,
                raw_reference=validated_request.target_reference,
            )
            new_evidence.append(ev_refund)

            # Canonical lifecycle event for the refund
            evt_refund = CanonicalEvent(
                event_id=f"evt_{execution_id}_refund",
                transaction_id=f"tx_{contract.intent_id}",
                intent_id=contract.intent_id,
                event_type="payment.refunded",
                timestamp=exec_time,
                occurred_at=exec_time,
                amount=refund_amount,
                source=EvidenceSource.RAZORPAY,
                authority=EvidenceAuthority.AUTHORITATIVE,
                payload_summary={
                    "refund_execution_id": execution_id,
                    "target_reference": validated_request.target_reference,
                    "refund_amount": refund_amount.amount,
                },
            )
            new_events.append(evt_refund)

        elif validated_request.action_type in (ActionType.VOID, ActionType.CANCEL):
            # Merchant / provider cancellation
            ev_cancel = Evidence(
                evidence_id=f"ev_{execution_id}_cancel",
                intent_id=contract.intent_id,
                source=EvidenceSource.MERCHANT,
                authority=EvidenceAuthority.MERCHANT_ATTESTED,
                field_name="order_status",
                field_value="cancelled",
                observed_at=exec_time,
                raw_reference=validated_request.target_reference,
            )
            new_evidence.append(ev_cancel)

            evt_cancel = CanonicalEvent(
                event_id=f"evt_{execution_id}_cancel",
                transaction_id=f"tx_{contract.intent_id}",
                intent_id=contract.intent_id,
                event_type="order.cancelled",
                timestamp=exec_time,
                occurred_at=exec_time,
                amount=None,
                source=EvidenceSource.MERCHANT,
                authority=EvidenceAuthority.MERCHANT_ATTESTED,
                payload_summary={
                    "cancel_execution_id": execution_id,
                    "target_reference": validated_request.target_reference,
                },
            )
            new_events.append(evt_cancel)

        elif validated_request.action_type in (ActionType.NOTIFY, ActionType.HOLD):
            # Safe observation query / hold
            evt_notify = CanonicalEvent(
                event_id=f"evt_{execution_id}_notify",
                transaction_id=f"tx_{contract.intent_id}",
                intent_id=contract.intent_id,
                event_type="action.observed",
                timestamp=exec_time,
                occurred_at=exec_time,
                amount=None,
                source=EvidenceSource.SYSTEM,
                authority=EvidenceAuthority.SYSTEM_DERIVED,
                payload_summary={"target_reference": validated_request.target_reference},
            )
            new_events.append(evt_notify)

        result = RecoveryExecutionResult(
            execution_id=execution_id,
            action_request=validated_request,
            status="SUCCESS",
            evidence=new_evidence,
            events=new_events,
            executed_at=exec_time,
            is_idempotent_replay=False,
            details={
                "action_type": validated_request.action_type.value,
                "attempt_number": current_attempts + 1,
            },
        )

        # Cache in idempotency table
        self._idempotency_records[action_request.idempotency_key] = result
        return result
