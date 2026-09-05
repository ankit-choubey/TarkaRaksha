"""
Transaction Orchestration Service for TarkaRaksha (T10).
Manages the complete vertical slice lifecycle:
Authorized Intent -> Gateway Order -> Checkout Completion -> Signature Verification ->
Authoritative Provider State -> Canonical Evidence -> Deterministic Verification -> PASS/DRIFT/UNKNOWN.
"""
from datetime import datetime, timezone, timedelta
import logging
import time
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.domain.models import (
    ActionRequest,
    ActionType,
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
    CreateTransactionRequest,
    CreateTransactionResponse,
    CompleteTransactionRequest,
    CompleteTransactionResponse,
    RecoverTransactionRequest,
)
from backend.app.domain.states import TransactionStateMachine
from backend.app.services.ai import parse_intent, AIProvider
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.mrdp import build_mrdp
from backend.app.services.payment import (
    PaymentNotFoundError,
    PaymentProvider,
    PaymentSignatureError,
    PaymentTimeoutError,
    RazorpayAdapter,
)
from backend.app.services.recovery import (
    MAX_RECOVERY_ATTEMPTS,
    InvalidRecoveryStateError,
    RecoverabilityStatus,
    RecoveryExhaustedError,
    RecoveryExecutor,
    UnsafeActionRequestError,
    classify_recovery,
    revalidate_recovery,
    validate_action_request,
)

logger = logging.getLogger(__name__)


class TransactionSession:
    """Holds active runtime context for a transaction slice in memory."""
    def __init__(
        self,
        transaction_id: str,
        intent: IntentContract,
        state_machine: TransactionStateMachine,
        order: ProviderOrder,
        created_at: datetime,
    ):
        self.transaction_id = transaction_id
        self.intent = intent
        self.state_machine = state_machine
        self.order = order
        self.payment: Optional[ProviderPayment] = None
        self.created_at = created_at
        self.updated_at = created_at
        self.completed_response: Optional[CompleteTransactionResponse] = None
        self.evidence_bundle: Optional[EvidenceBundle] = None
        self.integrity_result: Optional[IntegrityResult] = None
        self.events: List[CanonicalEvent] = []
        self.recovery_attempts: int = 0


class TransactionService:
    """
    Control plane orchestrator for protected transaction execution.
    Enforces deterministic integrity rules, state machine transitions,
    bounded provider polling, and strict signature verification.
    """

    def __init__(self, default_provider: Optional[PaymentProvider] = None):
        self._default_provider = default_provider
        self._sessions: Dict[str, TransactionSession] = {}
        self._intent_to_tx: Dict[str, str] = {}
        self._recovery_executor = RecoveryExecutor()

    @property
    def recovery_executor(self) -> RecoveryExecutor:
        return self._recovery_executor

    def get_provider(self, provider_override: Optional[PaymentProvider] = None) -> PaymentProvider:
        if provider_override is not None:
            return provider_override
        if self._default_provider is not None:
            return self._default_provider
        return RazorpayAdapter()

    def get_session(self, transaction_id: str) -> Optional[TransactionSession]:
        return self._sessions.get(transaction_id)

    def get_session_by_intent(self, intent_id: str) -> Optional[TransactionSession]:
        tx_id = self._intent_to_tx.get(intent_id)
        if tx_id:
            return self._sessions.get(tx_id)
        return None

    def create_transaction(
        self,
        request: CreateTransactionRequest,
        provider: Optional[PaymentProvider] = None,
        ai_provider: Optional[AIProvider] = None,
        now: Optional[datetime] = None,
    ) -> CreateTransactionResponse:
        """
        Step 1 & 2: Authorizes intent and creates bound order on payment gateway.
        """
        ts = now or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # 1. Resolve or Parse Intent
        if request.intent is not None:
            intent = request.intent
        elif request.natural_language_intent:
            intent = parse_intent(
                user_prompt=request.natural_language_intent,
                provider=ai_provider,
                issued_by=request.issued_by,
                issued_at=ts,
            )
        else:
            raise ValueError("Either intent or natural_language_intent must be provided")

        # 2. Intent-level duplicate defense
        if intent.intent_id in self._intent_to_tx:
            existing_tx_id = self._intent_to_tx[intent.intent_id]
            existing_session = self._sessions[existing_tx_id]
            logger.info("Intent %s already associated with transaction %s", intent.intent_id, existing_tx_id)
            return CreateTransactionResponse(
                transaction_id=existing_session.transaction_id,
                intent_id=intent.intent_id,
                order_id=existing_session.order.order_id,
                amount=existing_session.order.amount,
                currency=existing_session.order.currency,
                state=existing_session.state_machine.current_state,
                key_id=settings.razorpay_key_id,
                created_at=existing_session.created_at,
            )

        transaction_id = f"tx_{intent.intent_id}"
        payment_gateway = self.get_provider(provider)

        # 3. Initialize State Machine in CREATED
        state_machine = TransactionStateMachine(
            transaction_id=transaction_id,
            intent=intent,
            initial_state=TransactionState.CREATED,
            created_at=ts,
        )

        # 4. Create bound gateway order using integer minor units
        order_receipt = intent.intent_id
        order_notes = {
            "intent_id": intent.intent_id,
            "sku": intent.items[0].sku if intent.items else "N/A",
            "quantity": str(intent.items[0].quantity) if intent.items else "1",
        }
        order = payment_gateway.create_order(
            amount=intent.max_total,
            receipt=order_receipt,
            notes=order_notes,
        )

        # 5. Transition to EXECUTING
        exec_ts = ts + timedelta(milliseconds=10)
        state_machine.transition_to(
            to_state=TransactionState.EXECUTING,
            reason=f"Gateway order {order.order_id} created and bound to intent",
            timestamp=exec_ts,
            triggered_by="CONTROL_PLANE",
            is_verified=True,
            context={"order_id": order.order_id},
        )

        # 6. Store session
        session = TransactionSession(
            transaction_id=transaction_id,
            intent=intent,
            state_machine=state_machine,
            order=order,
            created_at=ts,
        )
        self._sessions[transaction_id] = session
        self._intent_to_tx[intent.intent_id] = transaction_id

        return CreateTransactionResponse(
            transaction_id=transaction_id,
            intent_id=intent.intent_id,
            order_id=order.order_id,
            amount=order.amount,
            currency=order.currency,
            state=state_machine.current_state,
            key_id=getattr(payment_gateway, "key_id", settings.razorpay_key_id),
            created_at=ts,
        )

    def complete_transaction(
        self,
        request: CompleteTransactionRequest,
        provider: Optional[PaymentProvider] = None,
        now: Optional[datetime] = None,
        poll_delay_seconds: float = 0.0,
    ) -> CompleteTransactionResponse:
        """
        Step 3-7: Verifies signature, polls provider for authoritative payment state,
        normalizes evidence, and executes deterministic integrity verification.
        """
        session = self.get_session(request.transaction_id)
        if not session:
            raise KeyError(f"Transaction '{request.transaction_id}' not found")

        # Idempotent return if already evaluated
        if session.completed_response is not None:
            return session.completed_response

        ts = now or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        payment_gateway = self.get_provider(provider)

        # Invariant: Order ID in completion request must match order bound to transaction
        if request.order_id != session.order.order_id:
            raise ValueError(
                f"Order ID '{request.order_id}' does not match bound order '{session.order.order_id}'"
            )

        # 1. Cryptographic Signature Verification
        # If signature verification fails, raises PaymentSignatureError and halts immediately.
        payment_gateway.verify_payment_signature(
            order_id=request.order_id,
            payment_id=request.payment_id,
            signature=request.signature,
        )

        # 2. Advance state machine: EXECUTING -> OBSERVING
        obs_ts = ts
        if obs_ts < session.state_machine.updated_at:
            obs_ts = session.state_machine.updated_at + timedelta(milliseconds=10)

        session.state_machine.transition_to(
            to_state=TransactionState.OBSERVING,
            reason=f"Signature verified for payment {request.payment_id}. Ingesting gateway state.",
            timestamp=obs_ts,
            triggered_by="GATEWAY_CALLBACK",
            is_verified=True,
            context={"payment_id": request.payment_id, "order_id": request.order_id},
        )

        # 3. Authoritative Provider State Retrieval with Bounded Polling (§7.37)
        payment = self._fetch_payment_with_bounded_polling(
            gateway=payment_gateway,
            payment_id=request.payment_id,
            poll_delay_seconds=poll_delay_seconds,
        )
        session.payment = payment

        # 4. Advance state machine: OBSERVING -> VERIFYING
        verif_ts = obs_ts + timedelta(milliseconds=10)
        session.state_machine.transition_to(
            to_state=TransactionState.VERIFYING,
            reason="Gateway evidence normalized. Running deterministic integrity checks.",
            timestamp=verif_ts,
            triggered_by="EVIDENCE_LAYER",
            is_verified=True,
            context={"payment_id": payment.payment_id if payment else request.payment_id},
        )

        # 5. Handle unresolved payment state (First-class UNKNOWN)
        if payment is None:
            unknown_result = IntegrityResult(
                evaluation_id=f"eval-{session.intent.intent_id}",
                intent_id=session.intent.intent_id,
                status=IntegrityStatus.UNKNOWN,
                evaluated_at=verif_ts,
                rule_results={"economic": False, "semantic": False, "temporal": False},
                violations=["Payment state could not be resolved from gateway within polling window"],
                evidence_ids=[],
                confidence_score=0.0,
                explanation="Missing authoritative gateway evidence",
            )
            eval_ts = verif_ts + timedelta(milliseconds=10)
            session.state_machine.apply_integrity_result(unknown_result, timestamp=eval_ts)
            empty_bundle = EvidenceBundle(
                bundle_id=f"b_{session.intent.intent_id}",
                intent_id=session.intent.intent_id,
                created_at=eval_ts,
                records=[],
            )
            mrdp_unknown = build_mrdp(
                contract=session.intent,
                integrity_result=unknown_result,
                evidence_bundle=empty_bundle,
                generated_at=eval_ts,
            )
            session.integrity_result = unknown_result
            session.evidence_bundle = empty_bundle
            
            response = CompleteTransactionResponse(
                transaction_id=session.transaction_id,
                intent_id=session.intent.intent_id,
                order_id=request.order_id,
                payment_id=request.payment_id,
                state=session.state_machine.current_state,
                integrity_status=IntegrityStatus.UNKNOWN,
                rule_results=unknown_result.rule_results,
                violations=unknown_result.violations,
                evidence_ids=[],
                mrdp=mrdp_unknown,
                verified_at=eval_ts,
            )
            session.completed_response = response
            return response

        # 6. Normalize Authoritative Gateway Evidence
        evidence_list = payment_gateway.normalize_payment_evidence(payment, session.intent.intent_id)

        # Ensure executed_items evidence is present from provider order/payment notes
        if not any(e.field_name == "executed_items" for e in evidence_list):
            notes = payment.notes or (session.order.notes if session.order else {})
            if "sku" in notes or "item_sku" in notes:
                sku = str(notes.get("sku") or notes.get("item_sku"))
                try:
                    qty = int(notes.get("quantity", 1))
                except (ValueError, TypeError):
                    qty = 1
                evidence_list.append(
                    Evidence(
                        evidence_id=f"ev_rzp_{payment.payment_id}_items",
                        intent_id=session.intent.intent_id,
                        source=EvidenceSource.RAZORPAY,
                        authority=EvidenceAuthority.AUTHORITATIVE,
                        field_name="executed_items",
                        field_value=[{"sku": sku, "quantity": qty}],
                        observed_at=payment.created_at,
                        raw_reference=payment.payment_id,
                    )
                )

        bundle = EvidenceBundle(
            bundle_id=f"b_{session.intent.intent_id}",
            intent_id=session.intent.intent_id,
            created_at=verif_ts,
            records=evidence_list,
        )
        session.evidence_bundle = bundle

        # Build canonical events for temporal integrity verification
        canonical_events: List[CanonicalEvent] = [
            CanonicalEvent(
                event_id=f"evt_ord_{session.order.order_id}",
                transaction_id=session.transaction_id,
                intent_id=session.intent.intent_id,
                event_type="order.created",
                timestamp=session.created_at,
                occurred_at=session.created_at,
                amount=session.order.amount,
                source=EvidenceSource.RAZORPAY,
                authority=EvidenceAuthority.AUTHORITATIVE,
                payload_summary={"order_id": session.order.order_id},
            ),
            CanonicalEvent(
                event_id=f"evt_pay_{payment.payment_id}",
                transaction_id=session.transaction_id,
                intent_id=session.intent.intent_id,
                event_type="payment.captured" if payment.captured else f"payment.{payment.status}",
                timestamp=payment.created_at,
                occurred_at=payment.created_at,
                amount=payment.amount,
                source=EvidenceSource.RAZORPAY,
                authority=EvidenceAuthority.AUTHORITATIVE,
                payload_summary={"payment_id": payment.payment_id, "status": payment.status},
            ),
        ]

        # 7. Execute Pure Deterministic Integrity Verification
        session.events = canonical_events
        eval_result = evaluate_integrity(
            contract=session.intent,
            evidence_list=evidence_list,
            events=canonical_events,
            reference_time=verif_ts,
        )
        session.integrity_result = eval_result

        # 8. Apply Deterministic Result to State Machine
        eval_ts = verif_ts + timedelta(milliseconds=10)
        session.state_machine.apply_integrity_result(eval_result, timestamp=eval_ts)

        # 9. If DRIFT or UNKNOWN, generate Machine-Readable Drift Proof (MRDP)
        mrdp_proof: Optional[MRDP] = None
        if eval_result.status in (IntegrityStatus.DRIFT, IntegrityStatus.UNKNOWN):
            mrdp_proof = build_mrdp(
                contract=session.intent,
                integrity_result=eval_result,
                evidence_bundle=bundle,
                generated_at=eval_ts,
            )

        response = CompleteTransactionResponse(
            transaction_id=session.transaction_id,
            intent_id=session.intent.intent_id,
            order_id=request.order_id,
            payment_id=request.payment_id,
            state=session.state_machine.current_state,
            integrity_status=eval_result.status,
            rule_results=eval_result.rule_results,
            violations=eval_result.violations,
            evidence_ids=eval_result.evidence_ids,
            mrdp=mrdp_proof,
            verified_at=eval_ts,
        )
        session.completed_response = response
        return response

    def _fetch_payment_with_bounded_polling(
        self,
        gateway: PaymentProvider,
        payment_id: str,
        poll_delay_seconds: float = 0.0,
    ) -> Optional[ProviderPayment]:
        """
        Bounded polling helper (§7.37):
        Attempts up to 3 times (immediately, +1s, +2s) to fetch authoritative payment.
        Returns ProviderPayment if found, None if unresolved.
        """
        for attempt in range(3):
            try:
                payment = gateway.fetch_payment(payment_id)
                if payment is not None:
                    return payment
            except (PaymentNotFoundError, PaymentTimeoutError) as exc:
                logger.warning("Polling attempt %d/3 for payment %s failed: %s", attempt + 1, payment_id, exc)
            except Exception as exc:
                logger.error("Unexpected error polling payment %s: %s", payment_id, exc)
                break

            if attempt < 2 and poll_delay_seconds > 0:
                time.sleep(poll_delay_seconds)

        return None

    def recover_transaction(
        self,
        request: RecoverTransactionRequest,
        provider: Optional[PaymentProvider] = None,
        ai_provider: Optional[AIProvider] = None,
        now: Optional[datetime] = None,
    ) -> CompleteTransactionResponse:
        """
        T11 Recovery Loop:
        DRIFT / RECOVERABLE UNKNOWN -> MRDP / Evidence -> Recovery Proposal ->
        Deterministic Safety Validation -> Bounded Recovery Action ->
        Observe -> Revalidate -> PASS / DRIFT / UNKNOWN / ABSTAIN.
        """
        session = self.get_session(request.transaction_id)
        if not session:
            raise KeyError(f"Transaction '{request.transaction_id}' not found")

        ts = now or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts <= session.state_machine.updated_at:
            ts = session.state_machine.updated_at + timedelta(milliseconds=10)

        # 1. State Guard: only DRIFT, UNKNOWN, RESOLVING, RECOVERING are legal
        current_state = session.state_machine.current_state
        if current_state == TransactionState.PASS:
            logger.info("Transaction %s already in PASS status. No recovery required.", session.transaction_id)
            return session.completed_response or CompleteTransactionResponse(
                transaction_id=session.transaction_id,
                intent_id=session.intent.intent_id,
                order_id=session.order.order_id,
                payment_id=session.payment.payment_id if session.payment else "N/A",
                state=TransactionState.PASS,
                integrity_status=IntegrityStatus.PASS,
                rule_results={"economic": True, "semantic": True, "temporal": True},
                violations=[],
                evidence_ids=[],
                mrdp=None,
                verified_at=ts,
            )

        if current_state == TransactionState.ABSTAIN:
            logger.info("Transaction %s is in terminal ABSTAIN state. No further actions.", session.transaction_id)
            return session.completed_response

        if current_state not in (
            TransactionState.DRIFT,
            TransactionState.UNKNOWN,
            TransactionState.RESOLVING,
            TransactionState.RECOVERING,
        ):
            raise InvalidRecoveryStateError(
                f"Cannot initiate recovery from state '{current_state.value}'. "
                "Recovery is permitted only from DRIFT, UNKNOWN, RESOLVING, or RECOVERING."
            )

        # 2. Recovery Attempts Limit Guard (§15)
        # Bounded at MAX_RECOVERY_ATTEMPTS (3). Attempt 4 forces ABSTAIN.
        if session.recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
            logger.warning(
                "Transaction %s exceeded max recovery attempts (%d). Transitioning to ABSTAIN.",
                session.transaction_id,
                MAX_RECOVERY_ATTEMPTS,
            )
            if session.state_machine.current_state != TransactionState.ABSTAIN:
                session.state_machine.transition_to(
                    to_state=TransactionState.ABSTAIN,
                    reason=f"Recovery attempt limit ({MAX_RECOVERY_ATTEMPTS}) reached. Escalating to ABSTAIN.",
                    timestamp=ts,
                    triggered_by="RECOVERY_POLICY",
                    is_verified=True,
                )
            prior_rule_results = session.integrity_result.rule_results if session.integrity_result else {}
            prior_violations = session.integrity_result.violations if session.integrity_result else []
            prior_ev_ids = session.integrity_result.evidence_ids if session.integrity_result else []
            response = CompleteTransactionResponse(
                transaction_id=session.transaction_id,
                intent_id=session.intent.intent_id,
                order_id=session.order.order_id,
                payment_id=session.payment.payment_id if session.payment else "unresolved",
                state=TransactionState.ABSTAIN,
                integrity_status=session.integrity_result.status if session.integrity_result else IntegrityStatus.DRIFT,
                rule_results=prior_rule_results,
                violations=[f"Recovery attempt limit ({MAX_RECOVERY_ATTEMPTS}) reached. Control plane escalated to ABSTAIN."] + prior_violations,
                evidence_ids=prior_ev_ids,
                mrdp=session.completed_response.mrdp if session.completed_response else None,
                verified_at=ts,
            )
            session.completed_response = response
            return response

        # 3. Deterministic Recovery Policy Classification (§5, §6)
        mrdp_obj = session.completed_response.mrdp if session.completed_response else None
        classification = classify_recovery(
            contract=session.intent,
            integrity_result=session.integrity_result or IntegrityResult(
                evaluation_id=f"eval_{session.intent.intent_id}",
                intent_id=session.intent.intent_id,
                status=IntegrityStatus.DRIFT,
                evaluated_at=ts,
                rule_results={},
                violations=[],
                evidence_ids=[],
                confidence_score=0.0,
            ),
            mrdp=mrdp_obj,
            current_attempt=session.recovery_attempts + 1,
            reference_time=ts,
        )

        if classification.status in (RecoverabilityStatus.NON_RECOVERABLE, RecoverabilityStatus.ABSTAIN) or not classification.is_recoverable:
            # Deterministically non-recoverable: transition directly to ABSTAIN (§5)
            logger.warning(
                "Transaction %s classified as %s: %s. Transitioning to ABSTAIN.",
                session.transaction_id,
                classification.status.value,
                classification.reason,
            )
            session.state_machine.transition_to(
                to_state=TransactionState.ABSTAIN,
                reason=classification.reason,
                timestamp=ts,
                triggered_by="RECOVERY_POLICY",
                is_verified=True,
            )
            response = CompleteTransactionResponse(
                transaction_id=session.transaction_id,
                intent_id=session.intent.intent_id,
                order_id=session.order.order_id,
                payment_id=session.payment.payment_id if session.payment else "unresolved",
                state=TransactionState.ABSTAIN,
                integrity_status=session.integrity_result.status if session.integrity_result else IntegrityStatus.DRIFT,
                rule_results=session.integrity_result.rule_results if session.integrity_result else {},
                violations=[classification.reason] + (session.integrity_result.violations if session.integrity_result else []),
                evidence_ids=session.integrity_result.evidence_ids if session.integrity_result else [],
                mrdp=mrdp_obj,
                verified_at=ts,
            )
            session.completed_response = response
            return response

        # 4. Formulate ActionRequest (§8)
        if request.action_request is not None:
            if isinstance(request.action_request, ActionRequest):
                action_req = request.action_request
            elif isinstance(request.action_request, dict):
                action_req = ActionRequest(**request.action_request)
            else:
                raise ValueError(f"Invalid action_request type: {type(request.action_request)}")
        else:
            # Deterministically synthesize compensatory ActionRequest
            target_ref = session.payment.payment_id if session.payment else session.order.order_id
            if classification.recommended_action == ActionType.REFUND and classification.max_allowed_amount:
                action_req = ActionRequest(
                    request_id=f"act_rec_{session.transaction_id}_{session.recovery_attempts + 1}",
                    intent_id=session.intent.intent_id,
                    action_type=ActionType.REFUND,
                    amount=classification.max_allowed_amount,
                    target_reference=target_ref,
                    idempotency_key=f"idemp_rec_{session.transaction_id}_{session.recovery_attempts + 1}",
                    requested_at=ts,
                    requested_by="AI_RECOVERY_AGENT" if request.use_ai else "CONTROL_PLANE_POLICY",
                )
            elif classification.recommended_action == ActionType.CANCEL:
                action_req = ActionRequest(
                    request_id=f"act_rec_{session.transaction_id}_{session.recovery_attempts + 1}",
                    intent_id=session.intent.intent_id,
                    action_type=ActionType.CANCEL,
                    amount=None,
                    target_reference=session.order.order_id,
                    idempotency_key=f"idemp_rec_{session.transaction_id}_{session.recovery_attempts + 1}",
                    requested_at=ts,
                    requested_by="CONTROL_PLANE_POLICY",
                )
            else:
                action_req = ActionRequest(
                    request_id=f"act_obs_{session.transaction_id}_{session.recovery_attempts + 1}",
                    intent_id=session.intent.intent_id,
                    action_type=ActionType.NOTIFY,
                    amount=None,
                    target_reference=target_ref,
                    idempotency_key=f"idemp_obs_{session.transaction_id}_{session.recovery_attempts + 1}",
                    requested_at=ts,
                    requested_by="CONTROL_PLANE_POLICY",
                )

        # 5. Deterministic Safety Validation of ActionRequest (§8, §9)
        try:
            validated_req = validate_action_request(
                action_request=action_req,
                contract=session.intent,
                mrdp=mrdp_obj,
                current_state=session.state_machine.current_state,
                attempt_count=session.recovery_attempts,
            )
        except (UnsafeActionRequestError, RecoveryExhaustedError, InvalidRecoveryStateError) as exc:
            logger.error("ActionRequest safety validation failed for %s: %s", session.transaction_id, exc)
            session.state_machine.transition_to(
                to_state=TransactionState.ABSTAIN,
                reason=f"ActionRequest safety validation failed: {exc}",
                timestamp=ts,
                triggered_by="SAFETY_VALIDATOR",
                is_verified=True,
            )
            response = CompleteTransactionResponse(
                transaction_id=session.transaction_id,
                intent_id=session.intent.intent_id,
                order_id=session.order.order_id,
                payment_id=session.payment.payment_id if session.payment else "unresolved",
                state=TransactionState.ABSTAIN,
                integrity_status=session.integrity_result.status if session.integrity_result else IntegrityStatus.DRIFT,
                rule_results=session.integrity_result.rule_results if session.integrity_result else {},
                violations=[f"Unsafe action request rejected: {exc}"] + (session.integrity_result.violations if session.integrity_result else []),
                evidence_ids=session.integrity_result.evidence_ids if session.integrity_result else [],
                mrdp=mrdp_obj,
                verified_at=ts,
            )
            session.completed_response = response
            return response

        # 6. State Machine: Enter RECOVERING or RESOLVING (§14)
        rec_ts = ts + timedelta(milliseconds=5)
        if session.state_machine.current_state == TransactionState.DRIFT:
            session.state_machine.transition_to(
                to_state=TransactionState.RECOVERING,
                reason=f"Executing compensatory action {validated_req.action_type.value}",
                timestamp=rec_ts,
                triggered_by="RECOVERY_LOOP",
                is_verified=True,
                context={"action_type": validated_req.action_type.value},
            )
        elif session.state_machine.current_state == TransactionState.UNKNOWN:
            session.state_machine.transition_to(
                to_state=TransactionState.RESOLVING,
                reason="Investigating unresolved transaction state via recovery query",
                timestamp=rec_ts,
                triggered_by="RESOLUTION_LOOP",
                is_verified=True,
            )

        # 7. Bounded Recovery Execution (§11)
        payment_gateway = self.get_provider(provider)
        exec_result = self._recovery_executor.execute(
            action_request=validated_req,
            contract=session.intent,
            provider=payment_gateway,
            current_state=session.state_machine.current_state,
            mrdp=mrdp_obj,
            now=rec_ts,
        )
        session.recovery_attempts += 1

        # 8. State Machine: Enter REVALIDATING (§12, §14)
        reval_ts = rec_ts + timedelta(milliseconds=10)
        session.state_machine.transition_to(
            to_state=TransactionState.REVALIDATING,
            reason="Recovery action executed. Running deterministic revalidation.",
            timestamp=reval_ts,
            triggered_by="REVALIDATOR",
            is_verified=True,
        )

        # 9. Deterministic Revalidation (§12)
        prior_evidence = session.evidence_bundle.records if session.evidence_bundle else []
        reval_result = revalidate_recovery(
            contract=session.intent,
            prior_evidence=prior_evidence,
            recovery_evidence=exec_result.evidence,
            prior_events=session.events,
            recovery_events=exec_result.events,
            reference_time=reval_ts,
        )
        session.integrity_result = reval_result

        # 10. Update Session Evidence and Events (§17)
        merged_evidence = list(prior_evidence) + list(exec_result.evidence)
        session.evidence_bundle = EvidenceBundle(
            bundle_id=f"b_{session.intent.intent_id}_post_rec",
            intent_id=session.intent.intent_id,
            created_at=reval_ts,
            records=merged_evidence,
        )
        session.events.extend(exec_result.events)

        # 11. Apply Deterministic Result to State Machine (§12)
        fin_ts = reval_ts + timedelta(milliseconds=10)
        session.state_machine.apply_integrity_result(reval_result, timestamp=fin_ts)

        # 12. Update MRDP if still DRIFT or UNKNOWN
        updated_mrdp: Optional[MRDP] = None
        if reval_result.status in (IntegrityStatus.DRIFT, IntegrityStatus.UNKNOWN):
            updated_mrdp = build_mrdp(
                contract=session.intent,
                integrity_result=reval_result,
                evidence_bundle=session.evidence_bundle,
                generated_at=fin_ts,
            )

        response = CompleteTransactionResponse(
            transaction_id=session.transaction_id,
            intent_id=session.intent.intent_id,
            order_id=session.order.order_id,
            payment_id=session.payment.payment_id if session.payment else "unresolved",
            state=session.state_machine.current_state,
            integrity_status=reval_result.status,
            rule_results=reval_result.rule_results,
            violations=reval_result.violations,
            evidence_ids=reval_result.evidence_ids,
            mrdp=updated_mrdp,
            verified_at=fin_ts,
        )
        session.completed_response = response
        return response
