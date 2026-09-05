"""
Safe Observation & Bounded UNKNOWN Resolution Engine for TarkaRaksha (T12).
Enforces the core invariants:
1. UNKNOWN resolution is strictly non-side-effecting: queries provider truth without moving money.
2. Defends against infinite loops with bounded attempt budgets (MAX_RESOLUTION_ATTEMPTS = 3).
3. Enforces deterministic resolution idempotency via idempotency keys.
4. Normalizes newly ingested evidence through canonical T06 representations.
5. Revalidates through pure T04 deterministic integrity verification.
"""
from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional

from backend.app.domain.evidence import analyze_bundle_conflicts
from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceBundle,
    EvidenceSource,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    Money,
    MRDP,
    ProviderOrder,
    ProviderPayment,
    TransactionState,
)
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.payment import (
    PaymentNotFoundError,
    PaymentProvider,
    PaymentTimeoutError,
)
from .contracts import (
    MAX_RESOLUTION_ATTEMPTS,
    InvalidResolutionStateError,
    ResolutionCategory,
    ResolutionConflictError,
    ResolutionExhaustedError,
    ResolutionResult,
    ResolutionStrategy,
)
from .policy import diagnose_unknown

logger = logging.getLogger(__name__)

# Legal lifecycle states for UNKNOWN resolution (§14)
LEGAL_RESOLUTION_STATES = {
    TransactionState.UNKNOWN,
    TransactionState.RESOLVING,
}


class UnknownObserver:
    """
    Control plane engine executing safe, non-side-effecting observations
    to resolve UNKNOWN transaction ambiguity.
    """

    def __init__(self):
        self._idempotency_records: Dict[str, ResolutionResult] = {}
        self._attempt_counts: Dict[str, int] = {}

    def get_attempt_count(self, intent_id: str) -> int:
        return self._attempt_counts.get(intent_id, 0)

    def reset_attempts(self, intent_id: str) -> None:
        if intent_id in self._attempt_counts:
            del self._attempt_counts[intent_id]

    def resolve(
        self,
        contract: IntentContract,
        order: ProviderOrder,
        payment_id: Optional[str],
        provider: PaymentProvider,
        current_state: TransactionState,
        prior_evidence: List[Evidence],
        prior_events: List[CanonicalEvent],
        mrdp: Optional[MRDP] = None,
        idempotency_key: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ResolutionResult:
        """
        Executes bounded, idempotent UNKNOWN resolution.
        Queries authoritative provider state, normalizes evidence, resolves conflicts,
        and executes pure deterministic integrity evaluation.
        """
        eval_time = now or datetime.now(timezone.utc)
        if eval_time.tzinfo is None:
            eval_time = eval_time.replace(tzinfo=timezone.utc)

        # 1. State Boundary Check (§14)
        if current_state not in LEGAL_RESOLUTION_STATES:
            raise InvalidResolutionStateError(
                f"Cannot execute UNKNOWN resolution from state '{current_state.value}'. "
                f"Resolution is permitted only from {sorted(s.value for s in LEGAL_RESOLUTION_STATES)}."
            )

        # 2. Idempotency Check (§10)
        idemp_key = idempotency_key or f"idemp_res_{contract.intent_id}_{self.get_attempt_count(contract.intent_id)}"
        if idemp_key in self._idempotency_records:
            cached = self._idempotency_records[idemp_key]
            logger.info("Idempotent UNKNOWN resolution replay for key '%s'. Returning cached result.", idemp_key)
            return ResolutionResult(
                resolution_id=f"replay_{cached.resolution_id}",
                category=cached.category,
                strategy=cached.strategy,
                new_evidence=cached.new_evidence,
                new_events=cached.new_events,
                integrity_result=cached.integrity_result,
                is_idempotent_replay=True,
                resolved_at=eval_time,
                details={"original_resolution_id": cached.resolution_id},
            )

        # 3. Attempt Budget Check (§9, §18)
        current_attempts = self.get_attempt_count(contract.intent_id)
        if current_attempts >= MAX_RESOLUTION_ATTEMPTS:
            raise ResolutionExhaustedError(
                f"Resolution attempt budget ({MAX_RESOLUTION_ATTEMPTS}) exhausted for intent '{contract.intent_id}'."
            )

        # 4. Deterministic Diagnosis (§4, §5)
        bundle = EvidenceBundle(
            bundle_id=f"b_{contract.intent_id}_res",
            intent_id=contract.intent_id,
            created_at=eval_time,
            records=prior_evidence,
        )
        diagnosis = diagnose_unknown(
            contract=contract,
            integrity_result=IntegrityResult(
                evaluation_id=f"eval_{contract.intent_id}",
                intent_id=contract.intent_id,
                status=IntegrityStatus.UNKNOWN,
                evaluated_at=eval_time,
                rule_results={},
                violations=[],
                evidence_ids=[],
                confidence_score=0.0,
            ),
            evidence_bundle=bundle,
            mrdp=mrdp,
            current_attempt=current_attempts + 1,
            reference_time=eval_time,
        )

        self._attempt_counts[contract.intent_id] = current_attempts + 1

        res_hash = hashlib.sha256(
            f"{contract.intent_id}:{idemp_key}:{eval_time.isoformat()}".encode("utf-8")
        ).hexdigest()[:12]
        resolution_id = f"res_{res_hash}"

        # If diagnosis is ABSTAIN (e.g. contract expired, conflicting top-tier evidence, budget exhausted)
        if diagnosis.category == ResolutionCategory.ABSTAIN:
            abstain_result = IntegrityResult(
                evaluation_id=f"eval_{resolution_id}",
                intent_id=contract.intent_id,
                status=IntegrityStatus.UNKNOWN,  # IntegrityStatus has PASS/DRIFT/UNKNOWN; state becomes ABSTAIN
                evaluated_at=eval_time,
                rule_results={"EconomicIntegrityRule": False, "SemanticIntegrityRule": False, "TemporalIntegrityRule": False},
                violations=[diagnosis.reason],
                evidence_ids=[],
                confidence_score=0.0,
                explanation=diagnosis.reason,
            )
            result = ResolutionResult(
                resolution_id=resolution_id,
                category=ResolutionCategory.ABSTAIN,
                strategy=diagnosis.strategy,
                new_evidence=[],
                new_events=[],
                integrity_result=abstain_result,
                is_idempotent_replay=False,
                resolved_at=eval_time,
                details={"reason": diagnosis.reason},
            )
            self._idempotency_records[idemp_key] = result
            return result

        # 5. Safe Provider Observation (§7, §8)
        observed_payment: Optional[ProviderPayment] = None
        try:
            if diagnosis.strategy == ResolutionStrategy.FETCH_PAYMENT and payment_id:
                observed_payment = provider.fetch_payment(payment_id)
            elif diagnosis.strategy in (ResolutionStrategy.FETCH_ORDER_PAYMENTS, ResolutionStrategy.FETCH_PAYMENT):
                order_payments = provider.fetch_order_payments(order.order_id)
                if order_payments:
                    # Pick most recent authoritative payment for order
                    observed_payment = order_payments[-1]
                elif payment_id:
                    observed_payment = provider.fetch_payment(payment_id)
        except (PaymentNotFoundError, PaymentTimeoutError) as exc:
            logger.warning("Provider observation query failed: %s", exc)
            observed_payment = None
        except Exception as exc:
            logger.error("Unexpected error during provider observation: %s", exc)
            observed_payment = None

        new_evidence: List[Evidence] = []
        new_events: List[CanonicalEvent] = []

        # 6. Normalize Ingested Evidence (§6)
        if observed_payment is not None:
            new_evidence = provider.normalize_payment_evidence(observed_payment, contract.intent_id)

            # Ensure executed_items evidence is present from notes
            if not any(e.field_name == "executed_items" for e in new_evidence):
                notes = observed_payment.notes or order.notes or {}
                sku = str(notes.get("sku") or notes.get("item_sku") or (contract.items[0].sku if contract.items else "N/A"))
                qty_str = notes.get("quantity", "1")
                try:
                    qty = int(qty_str)
                except (ValueError, TypeError):
                    qty = 1
                new_evidence.append(
                    Evidence(
                        evidence_id=f"ev_res_{observed_payment.payment_id}_items",
                        intent_id=contract.intent_id,
                        source=EvidenceSource.RAZORPAY,
                        authority=EvidenceAuthority.AUTHORITATIVE,
                        field_name="executed_items",
                        field_value=[{"sku": sku, "quantity": qty}],
                        observed_at=observed_payment.created_at,
                        raw_reference=observed_payment.payment_id,
                    )
                )

            # Canonical lifecycle event for newly resolved payment
            new_events.append(
                CanonicalEvent(
                    event_id=f"evt_res_{observed_payment.payment_id}",
                    transaction_id=f"tx_{contract.intent_id}",
                    intent_id=contract.intent_id,
                    event_type="payment.captured" if observed_payment.captured else f"payment.{observed_payment.status}",
                    timestamp=observed_payment.created_at,
                    occurred_at=observed_payment.created_at,
                    amount=observed_payment.amount,
                    source=EvidenceSource.RAZORPAY,
                    authority=EvidenceAuthority.AUTHORITATIVE,
                    payload_summary={
                        "payment_id": observed_payment.payment_id,
                        "status": observed_payment.status,
                        "resolution_id": resolution_id,
                    },
                )
            )

        # 7. Merge Evidence and Reconcile Conflicts (T06)
        all_evidence = list(prior_evidence) + list(new_evidence)
        all_events = list(prior_events) + list(new_events)

        # 8. Deterministic Re-Verification (T04)
        integrity_eval = evaluate_integrity(
            contract=contract,
            evidence_list=all_evidence,
            events=all_events,
            reference_time=eval_time,
        )

        # Determine category based on deterministic verdict
        if integrity_eval.status == IntegrityStatus.PASS:
            category = ResolutionCategory.RESOLVABLE
        elif integrity_eval.status == IntegrityStatus.DRIFT:
            category = ResolutionCategory.RESOLVABLE  # Drift established; hand over to T11
        else:
            category = ResolutionCategory.REMAINS_UNKNOWN

        result = ResolutionResult(
            resolution_id=resolution_id,
            category=category,
            strategy=diagnosis.strategy,
            new_evidence=new_evidence,
            new_events=new_events,
            integrity_result=integrity_eval,
            is_idempotent_replay=False,
            resolved_at=eval_time,
            details={
                "attempt_number": current_attempts + 1,
                "observed_payment_id": observed_payment.payment_id if observed_payment else None,
                "verdict": integrity_eval.status.value,
            },
        )

        self._idempotency_records[idemp_key] = result
        return result
