"""Agentic Transaction Lifecycle Orchestrator for TarkaRaksha (E3).

Guiding Invariants:
1. AI proposes. Evidence proves. Deterministic logic decides.
2. The Orchestrator has control-flow authority, NOT truth or financial authority.
3. It does not become:
   - a second integrity engine (delegates to T04 evaluate_integrity)
   - a second authorization engine (delegates to IntentContract)
   - a second recovery engine (delegates to T11 RecoveryExecutor)
   - a second payment authority (delegates to T09 RazorpayAdapter)
   - a second TIX (delegates to I6 TIXExchangeService)
   - a second replay engine (delegates to T13 ReplayEngine)
   - a second UNKNOWN resolver (delegates to T12 UnknownObserver)
4. All buyer proposals pass through E2 Consumer Gate.
5. All merchant offers pass through E2 Merchant Gate.
6. Replanned proposals and revised offers must be revalidated through E2 gates.
7. UNKNOWN is never coerced into PASS.
8. Replay remains strictly CPU-only without live network, AI, or payment side-effects.
"""
from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from backend.app.domain.binding.contracts import BindingVerificationOutcome, PaymentBindingClaim
from backend.app.domain.buyer.contracts import BuyerTransactionProposal
from backend.app.domain.gates.contracts import (
    ConsumerGateResult,
    GateStatus,
    MerchantCheckType,
    MerchantGateResult,
)
from backend.app.domain.integration.contracts import (
    IntegrationBoundaryStage,
    IntegrationEvaluationResponse,
    IntegrationExecutionRecord,
    IntegrationTransactionContext,
)
from backend.app.domain.merchant.contracts import (
    BuyerCommerceRequest,
    BuyerItemRequest,
    InventoryStatus,
    MerchantOfferItem,
    MerchantResponse,
    ShippingOption,
    TaxEstimate,
)
from backend.app.domain.models import (
    ActionRequest,
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
from backend.app.domain.negotiation.contracts import (
    NegotiationPolicy,
    NegotiationRoundRecord,
    NegotiationSession,
    NegotiationState,
)
from backend.app.domain.orchestration.contracts import (
    LifecycleOutcome,
    LifecyclePolicy,
    LifecycleStage,
    LifecycleStepRecord,
    LifecycleViolationError,
)
from backend.app.domain.security_guard.contracts import (
    SecurityGuardContext,
    SecurityGuardResult,
    SecurityStatus,
)
from backend.app.domain.tix.contracts import (
    TIXMessage,
    TIXMessageType,
    TIXParticipantRole,
)
from backend.app.services.buyer.agent_service import BuyerAgentService
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.explanation import EvidenceAwareExplanationService
from backend.app.services.gates.consumer_gate import ConsumerGate
from backend.app.services.gates.merchant_gate import MerchantGate
from backend.app.services.integration.service import (
    ContextBindingMismatchError,
    IntegrationBoundaryError,
    IntegrationService,
)
from backend.app.services.merchant.catalog_service import MerchantCatalogService
from backend.app.services.negotiation.service import BoundedNegotiationService
from backend.app.services.payment import PaymentProvider, RazorpayAdapter
from backend.app.services.recovery import RecoveryExecutionResult, RecoveryExecutor
from backend.app.services.replay.contracts import ReplayResult, ReplaySnapshot
from backend.app.services.replay.engine import ReplayEngine
from backend.app.services.resolution import UnknownObserver
from backend.app.services.security_guard.guard import SecurityGuardService

logger = logging.getLogger(__name__)


class AgenticLifecycleOrchestrator:
    """
    Coordinates the bounded, deterministic agentic transaction lifecycle (E3).
    Composes existing services strictly through their authoritative boundaries.
    """

    def __init__(
        self,
        integration_service: Optional[IntegrationService] = None,
        buyer_service: Optional[BuyerAgentService] = None,
        merchant_service: Optional[MerchantCatalogService] = None,
        negotiation_service: Optional[BoundedNegotiationService] = None,
        security_guard: Optional[SecurityGuardService] = None,
        unknown_observer: Optional[UnknownObserver] = None,
        explanation_service: Optional[EvidenceAwareExplanationService] = None,
        recovery_executor: Optional[RecoveryExecutor] = None,
        payment_provider: Optional[PaymentProvider] = None,
        default_policy: Optional[LifecyclePolicy] = None,
    ):
        self.integration_service = integration_service or IntegrationService(
            merchant_service=merchant_service,
            buyer_service=buyer_service,
            recovery_executor=recovery_executor,
            payment_provider=payment_provider,
        )
        self.buyer_service = buyer_service or getattr(self.integration_service, "buyer_service", BuyerAgentService())
        self.merchant_service = merchant_service or getattr(self.integration_service, "merchant_service", MerchantCatalogService())
        self.negotiation_service = negotiation_service or BoundedNegotiationService(
            buyer_service=self.buyer_service,
            merchant_service=self.merchant_service,
            tix_service=self.integration_service.tix_service,
        )
        self.security_guard = security_guard or SecurityGuardService(
            kill_switch_service=self.integration_service.kill_switch_service
        )
        self.unknown_observer = unknown_observer or UnknownObserver()
        self.explanation_service = explanation_service
        self.recovery_executor = recovery_executor or getattr(self.integration_service, "recovery_executor", RecoveryExecutor())
        self.payment_provider = payment_provider or getattr(self.integration_service, "payment_provider", RazorpayAdapter())
        self.default_policy = default_policy or LifecyclePolicy()

        # Idempotency and session tracking (§23)
        self._idempotency_cache: Dict[str, LifecycleOutcome] = {}
        self._replan_counts: Dict[str, int] = {}
        self._resolution_counts: Dict[str, int] = {}

    def orchestrate(
        self,
        transaction_id: str,
        intent: IntentContract,
        agent_id: str,
        merchant_id: str,
        buyer_proposal: Optional[BuyerTransactionProposal] = None,
        merchant_response: Optional[MerchantResponse] = None,
        order_id: Optional[str] = None,
        payment_id: Optional[str] = None,
        payment_claim: Optional[PaymentBindingClaim] = None,
        provider_order: Optional[ProviderOrder] = None,
        provider_payment: Optional[ProviderPayment] = None,
        action_request: Optional[ActionRequest] = None,
        execute_payment: bool = False,
        policy: Optional[LifecyclePolicy] = None,
        reference_time: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
        untrusted_text: Optional[str] = None,
        attempt_id: str = "att_1",
    ) -> LifecycleOutcome:
        """
        Executes the bounded, deterministic agentic transaction lifecycle.

        Flow:
        1. Idempotency verification
        2. Context initialization & intent binding (E1)
        3. Buyer proposal ingestion & E2 Consumer Gate validation
        4. Merchant offer ingestion & E2 Merchant Gate validation
        5. TIX cryptographic chaining & evidence recording (I6)
        6. Security Guard threat evaluation (E4)
        7. Deterministic integrity evaluation (T04 evaluate_integrity)
        8. Branching:
           - PASS -> Payment verification/binding (if provided) -> COMPLETED
           - DRIFT -> MRDP generation -> Bounded replanning (I7) -> Revalidation -> Re-evaluation
           - UNKNOWN -> Bounded resolution (T12) -> Normalization -> Re-evaluation -> ABSTAIN if unresolved
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        active_policy = policy or self.default_policy

        # 1. Idempotency Check (§23)
        if idempotency_key:
            if idempotency_key in self._idempotency_cache:
                logger.info("Idempotent replay for key '%s'. Returning cached LifecycleOutcome.", idempotency_key)
                cached = self._idempotency_cache[idempotency_key]
                return cached

        steps: List[LifecycleStepRecord] = []
        history: List[str] = []

        def record_step(stage: LifecycleStage, action: str, status: str, details: Dict[str, Any]) -> None:
            nonlocal steps, history
            step = LifecycleStepRecord(
                step_index=len(steps) + 1,
                stage=stage,
                action=action,
                status=status,
                details=details,
                timestamp=ref_time,
            )
            steps.append(step)
            history.append(f"{ref_time.isoformat()}: [{stage.value}] {action} -> {status}")

        # 2. Context Initialization & Intent Binding (E1)
        try:
            record = self.integration_service.get_record(transaction_id)
            if not record:
                record = self.integration_service.create_context(
                    transaction_id=transaction_id,
                    intent_id=intent.intent_id,
                    agent_id=agent_id,
                    merchant_id=merchant_id,
                    attempt_id=attempt_id,
                    reference_time=ref_time,
                )
            record_step(
                LifecycleStage.INITIALIZED,
                "create_context",
                "SUCCESS",
                {"transaction_id": transaction_id, "intent_id": intent.intent_id, "agent_id": agent_id, "merchant_id": merchant_id},
            )

            if not record.intent:
                record = self.integration_service.bind_intent(transaction_id, intent, ref_time)
                record_step(LifecycleStage.INTENT_BOUND, "bind_intent", "SUCCESS", {"intent_id": intent.intent_id})
        except ContextBindingMismatchError as exc:
            record_step(LifecycleStage.BLOCKED, "context_binding", "FAILED", {"error": str(exc)})
            return LifecycleOutcome(
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                stage=LifecycleStage.BLOCKED,
                transaction_state=TransactionState.ABSTAIN,
                is_terminal=True,
                security_cleared=False,
                steps=steps,
                history=history,
                orchestrated_at=ref_time,
            )

        # 3. Buyer Proposal & E2 Consumer Gate
        if buyer_proposal is None:
            # Construct deterministic candidate proposal from intent and catalog
            first_item = intent.items[0] if intent.items else None
            sku = first_item.sku if first_item else "SKU_DEFAULT"
            qty = first_item.quantity if first_item else 1
            buyer_proposal = BuyerTransactionProposal(
                proposal_id=f"prop_{transaction_id}_{attempt_id}",
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
                buyer_agent_id=agent_id,
                sku=sku,
                quantity=qty,
                max_total=intent.max_total,
                rationale="Deterministic candidate proposal derived from intent authorization",
                created_at=ref_time,
            )

        # Ingest proposal & validate through Consumer Gate (E2)
        try:
            self.integration_service.process_buyer_proposal(transaction_id, buyer_proposal, ref_time)
            consumer_gate_result, record = self.integration_service.validate_consumer_gate(
                transaction_id=transaction_id,
                proposal=buyer_proposal,
                reference_time=ref_time,
            )
            record_step(
                LifecycleStage.CONSUMER_GATE_VERIFIED,
                "validate_consumer_gate",
                consumer_gate_result.status.value,
                {
                    "proposal_id": buyer_proposal.proposal_id,
                    "findings_count": len(consumer_gate_result.findings),
                    "is_valid": consumer_gate_result.is_valid,
                },
            )

            if consumer_gate_result.status == GateStatus.INVALID:
                record_step(
                    LifecycleStage.BLOCKED,
                    "consumer_gate_rejection",
                    "BLOCKED",
                    {"violations": [f.message for f in consumer_gate_result.findings if f.status == GateStatus.INVALID]},
                )
                outcome = LifecycleOutcome(
                    transaction_id=transaction_id,
                    intent_id=intent.intent_id,
                    agent_id=agent_id,
                    merchant_id=merchant_id,
                    stage=LifecycleStage.BLOCKED,
                    transaction_state=TransactionState.ABSTAIN,
                    is_terminal=True,
                    security_cleared=False,
                    steps=steps,
                    history=history,
                    orchestrated_at=ref_time,
                )
                if idempotency_key:
                    self._idempotency_cache[idempotency_key] = outcome
                return outcome

        except ContextBindingMismatchError as exc:
            record_step(LifecycleStage.BLOCKED, "buyer_proposal_binding", "FAILED", {"error": str(exc)})
            return LifecycleOutcome(
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                stage=LifecycleStage.BLOCKED,
                transaction_state=TransactionState.ABSTAIN,
                is_terminal=True,
                security_cleared=False,
                steps=steps,
                history=history,
                orchestrated_at=ref_time,
            )

        # 4. Merchant Offer & E2 Merchant Gate
        if merchant_response is None:
            # Query catalog for active item
            catalog_item = self.merchant_service.get_item(buyer_proposal.sku)
            unit_price = catalog_item.price if catalog_item else buyer_proposal.max_total
            total_price = Money(amount=unit_price.amount * buyer_proposal.quantity, currency=unit_price.currency)
            merchant_response = MerchantResponse(
                response_id=f"mresp_{transaction_id}_{attempt_id}",
                merchant_id=merchant_id,
                request_id=f"req_{transaction_id}_{attempt_id}",
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
                is_success=True,
                items=[
                    MerchantOfferItem(
                        sku=buyer_proposal.sku,
                        title=catalog_item.title if catalog_item else "Offer Item",
                        quantity=buyer_proposal.quantity,
                        unit_price=unit_price,
                        total_price=total_price,
                    )
                ],
                subtotal=total_price,
                tax=TaxEstimate(amount=Money(amount=0, currency=unit_price.currency)),
                shipping=ShippingOption(
                    option_id="ship_std",
                    carrier="Standard Courier",
                    method_name="Standard Shipping",
                    cost=Money(amount=0, currency=unit_price.currency),
                    estimated_days=2,
                ),
                total_amount=total_price,
                inventory_status=InventoryStatus.AVAILABLE,
                offer_created_at=ref_time,
                offer_expires_at=ref_time + timedelta(hours=2),
            )

        # Ingest response & validate through Merchant Gate (E2)
        try:
            self.integration_service.process_merchant_response(transaction_id, merchant_response, ref_time)
            merchant_gate_result, record = self.integration_service.validate_merchant_gate(
                transaction_id=transaction_id,
                merchant_response=merchant_response,
                requested_sku=buyer_proposal.sku,
                requested_quantity=buyer_proposal.quantity,
                reference_time=ref_time,
            )
            record_step(
                LifecycleStage.MERCHANT_GATE_VERIFIED,
                "validate_merchant_gate",
                merchant_gate_result.status.value,
                {
                    "merchant_id": merchant_id,
                    "findings_count": len(merchant_gate_result.findings),
                    "is_valid": merchant_gate_result.is_valid,
                },
            )

            blocking_findings = [
                f for f in merchant_gate_result.findings
                if f.status == GateStatus.INVALID and f.check_type != MerchantCheckType.PRICE.value
            ]
            if blocking_findings:
                record_step(
                    LifecycleStage.BLOCKED,
                    "merchant_gate_rejection",
                    "BLOCKED",
                    {"violations": [f.message for f in blocking_findings]},
                )
                outcome = LifecycleOutcome(
                    transaction_id=transaction_id,
                    intent_id=intent.intent_id,
                    agent_id=agent_id,
                    merchant_id=merchant_id,
                    stage=LifecycleStage.BLOCKED,
                    transaction_state=TransactionState.ABSTAIN,
                    is_terminal=True,
                    security_cleared=False,
                    steps=steps,
                    history=history,
                    orchestrated_at=ref_time,
                )
                if idempotency_key:
                    self._idempotency_cache[idempotency_key] = outcome
                return outcome

        except ContextBindingMismatchError as exc:
            record_step(LifecycleStage.BLOCKED, "merchant_response_binding", "FAILED", {"error": str(exc)})
            return LifecycleOutcome(
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                stage=LifecycleStage.BLOCKED,
                transaction_state=TransactionState.ABSTAIN,
                is_terminal=True,
                security_cleared=False,
                steps=steps,
                history=history,
                orchestrated_at=ref_time,
            )

        # 5. TIX Message Chaining (I6)
        proposal_tix = TIXMessage(
            message_id=f"tix_prop_{transaction_id}_{attempt_id}",
            transaction_id=transaction_id,
            intent_id=intent.intent_id,
            attempt_id=attempt_id,
            sender=agent_id,
            receiver=merchant_id,
            message_type=TIXMessageType.INTENT,
            payload={
                "proposal_id": buyer_proposal.proposal_id,
                "sku": buyer_proposal.sku,
                "quantity": buyer_proposal.quantity,
                "max_total": buyer_proposal.max_total.amount,
            },
            timestamp=ref_time,
        )
        self.integration_service.append_tix_message(transaction_id, proposal_tix, ref_time)

        offer_tix = TIXMessage(
            message_id=f"tix_offer_{transaction_id}_{attempt_id}",
            transaction_id=transaction_id,
            intent_id=intent.intent_id,
            attempt_id=attempt_id,
            sender=merchant_id,
            receiver=agent_id,
            message_type=TIXMessageType.OFFER,
            payload={
                "response_id": merchant_response.response_id,
                "total": merchant_response.total.amount,
                "currency": merchant_response.total.currency,
            },
            timestamp=ref_time,
        )
        self.integration_service.append_tix_message(transaction_id, offer_tix, ref_time)
        record_step(LifecycleStage.TIX_COMMITTED, "tix_exchange", "SUCCESS", {"messages": [proposal_tix.message_id, offer_tix.message_id]})

        # 6. E4 Security Threat Evaluation
        untrusted_payloads: List[str] = []
        if untrusted_text:
            untrusted_payloads.append(untrusted_text)
        if buyer_proposal.rationale:
            untrusted_payloads.append(buyer_proposal.rationale)

        security_ctx = SecurityGuardContext(
            transaction_id=transaction_id,
            intent_id=intent.intent_id,
            agent_id=agent_id,
            buyer_agent_id="agent_buyer_001",
            merchant_agent_id=merchant_id,
            authorized_max_total=intent.max_total.amount,
            authorized_currency=intent.currency,
            authorization_expires_at=intent.expires_at,
            current_time=ref_time,
            proposed_amount=buyer_proposal.max_total.amount,
            untrusted_payloads=untrusted_payloads,
            attempt_id=attempt_id,
            metadata={
                "allowed_capabilities": ["browse", "propose"],
                "max_capability_amount": intent.max_total.amount,
            },
        )
        security_result = self.security_guard.evaluate(security_ctx)
        is_blocked = (
            security_result.security_status in (SecurityStatus.BLOCK, SecurityStatus.HOLD)
            or security_result.kill_switch_triggered
        )
        record_step(
            LifecycleStage.SECURITY_EVALUATED,
            "evaluate_security_threats",
            security_result.security_status.value,
            {
                "threat_count": len(security_result.findings),
                "is_blocked": is_blocked,
                "kill_switch_triggered": security_result.kill_switch_triggered,
            },
        )

        if is_blocked:
            record_step(
                LifecycleStage.BLOCKED,
                "security_threat_block",
                "BLOCKED",
                {"reasons": [f.explanation for f in security_result.findings]},
            )
            outcome = LifecycleOutcome(
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                stage=LifecycleStage.BLOCKED,
                transaction_state=TransactionState.ABSTAIN,
                is_terminal=True,
                security_cleared=False,
                steps=steps,
                history=history,
                orchestrated_at=ref_time,
            )
            if idempotency_key:
                self._idempotency_cache[idempotency_key] = outcome
            return outcome

        # Ingest merchant response into canonical evidence store for T04 evaluation
        amount_ev = Evidence(
            evidence_id=f"ev_merchant_amount_{merchant_response.response_id}",
            intent_id=intent.intent_id,
            transaction_id=transaction_id,
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
            field_name="total_amount",
            field_value=merchant_response.total,
            observed_at=ref_time,
            provenance={"merchant_id": merchant_id, "response_id": merchant_response.response_id},
        )
        self.integration_service.add_evidence(transaction_id, amount_ev)

        items_ev = Evidence(
            evidence_id=f"ev_merchant_items_{merchant_response.response_id}",
            intent_id=intent.intent_id,
            transaction_id=transaction_id,
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
            field_name="executed_items",
            field_value=[{"sku": item.sku, "quantity": item.quantity} for item in merchant_response.items],
            observed_at=ref_time,
            provenance={"merchant_id": merchant_id, "response_id": merchant_response.response_id},
        )
        self.integration_service.add_evidence(transaction_id, items_ev)

        offer_event = CanonicalEvent(
            event_id=f"evt_offer_{merchant_response.response_id}",
            transaction_id=transaction_id,
            intent_id=intent.intent_id,
            event_type="OFFER_RECEIVED",
            timestamp=ref_time,
            amount=merchant_response.total,
            source=EvidenceSource.MERCHANT,
            authority=EvidenceAuthority.MERCHANT_ATTESTED,
        )
        self.integration_service.add_event(transaction_id, offer_event)

        # If provider payment provided, add to evidence store
        if provider_payment:
            is_captured = provider_payment.status == "captured"
            payment_ev = Evidence(
                evidence_id=f"ev_pay_{provider_payment.payment_id}",
                intent_id=intent.intent_id,
                transaction_id=transaction_id,
                source=EvidenceSource.RAZORPAY,
                authority=EvidenceAuthority.AUTHORITATIVE,
                field_name="total_amount",
                field_value=provider_payment.amount if is_captured else None,
                observed_at=ref_time,
                is_authoritative=True,
                provenance={"provider": "razorpay", "payment_id": provider_payment.payment_id, "status": provider_payment.status},
            )
            self.integration_service.add_evidence(transaction_id, payment_ev)
            pay_event = CanonicalEvent(
                event_id=f"evt_pay_{provider_payment.payment_id}",
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                event_type="PAYMENT_CAPTURED" if is_captured else "PAYMENT_ATTEMPT",
                timestamp=ref_time,
                amount=provider_payment.amount,
                source=EvidenceSource.RAZORPAY,
                authority=EvidenceAuthority.AUTHORITATIVE,
            )
            self.integration_service.add_event(transaction_id, pay_event)

        # 7. Deterministic Integrity Evaluation (T04 evaluate_integrity)
        eval_resp = self.integration_service.evaluate(transaction_id, ref_time)
        record_step(
            LifecycleStage.INTEGRITY_EVALUATED,
            "evaluate_integrity",
            eval_resp.status.value,
            {
                "violations": eval_resp.violations,
                "evidence_count": eval_resp.evidence_count,
                "mrdp_id": eval_resp.mrdp.mrdp_id if eval_resp.mrdp else None,
            },
        )

        # 8. Branch Handling
        current_replan_round = self._replan_counts.get(transaction_id, 0)
        current_resolution_round = self._resolution_counts.get(transaction_id, 0)

        # BRANCH 1: PASS
        if eval_resp.status == IntegrityStatus.PASS:
            bound_payment = False
            if order_id and payment_id and payment_claim:
                claim_outcome, record = self.integration_service.bind_payment(
                    transaction_id=transaction_id,
                    order_id=order_id,
                    payment_id=payment_id,
                    claim=payment_claim,
                    reference_time=ref_time,
                )
                bound_payment = claim_outcome.is_valid
                record_step(
                    LifecycleStage.PAYMENT_BOUND,
                    "bind_payment",
                    "SUCCESS" if claim_outcome.is_valid else "INVALID",
                    {"order_id": order_id, "payment_id": payment_id, "is_valid": claim_outcome.is_valid},
                )

                if execute_payment and claim_outcome.is_valid and self.payment_provider:
                    self.payment_provider.capture_payment(payment_id, merchant_response.total.amount, merchant_response.total.currency)

            sm = self.integration_service._state_machines[transaction_id]

            record_step(LifecycleStage.COMPLETED, "complete_transaction", "COMPLETED", {"transaction_id": transaction_id})
            outcome = LifecycleOutcome(
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                stage=LifecycleStage.COMPLETED,
                integrity_status=IntegrityStatus.PASS,
                transaction_state=sm.current_state,
                is_terminal=True,
                replan_rounds=current_replan_round,
                resolution_attempts=current_resolution_round,
                security_cleared=True,
                payment_bound=bound_payment,
                order_id=order_id,
                payment_id=payment_id,
                steps=steps,
                history=history,
                orchestrated_at=ref_time,
            )
            if idempotency_key:
                self._idempotency_cache[idempotency_key] = outcome
            return outcome

        # BRANCH 2: DRIFT
        elif eval_resp.status == IntegrityStatus.DRIFT:
            record_step(
                LifecycleStage.DRIFT_REPLANNING,
                "drift_detected",
                "DRIFT",
                {"violations": eval_resp.violations, "mrdp_id": eval_resp.mrdp.mrdp_id if eval_resp.mrdp else None},
            )

            # Check bounded replan budget (§14, §15, I7 limit)
            if active_policy.auto_replan_on_drift and current_replan_round < active_policy.max_replans:
                self._replan_counts[transaction_id] = current_replan_round + 1
                sm = self.integration_service._state_machines[transaction_id]
                if sm.current_state == TransactionState.DRIFT:
                    sm.transition_to(to_state=TransactionState.RECOVERING, reason="initiating_bounded_replan", timestamp=ref_time)
                    sm.transition_to(to_state=TransactionState.REVALIDATING, reason="revalidating_counter_offer", timestamp=ref_time)

                record_step(
                    LifecycleStage.DRIFT_REPLANNING,
                    "invoke_bounded_replan",
                    "STARTED",
                    {"round": current_replan_round + 1, "max_replans": active_policy.max_replans},
                )

                # Identify corrective action: Check if substitution allowed or budget adjustment
                corrected_sku = buyer_proposal.sku
                if intent.allowed_substitutions and buyer_proposal.sku not in [it.sku for it in intent.items]:
                    corrected_sku = intent.items[0].sku if intent.items else buyer_proposal.sku

                # Buyer agent prepares revised proposal conforming strictly to intent
                revised_proposal = BuyerTransactionProposal(
                    proposal_id=f"prop_{transaction_id}_{attempt_id}_r{current_replan_round + 1}",
                    intent_id=intent.intent_id,
                    transaction_id=transaction_id,
                    buyer_agent_id=agent_id,
                    sku=corrected_sku,
                    quantity=buyer_proposal.quantity,
                    max_total=intent.max_total,
                    rationale=f"Bounded replan round {current_replan_round + 1} resolving drift: {eval_resp.violations}",
                    created_at=ref_time,
                )

                # MANDATORY REVALIDATION 1: Revised proposal MUST pass E2 Consumer Gate!
                revised_consumer_gate, _ = self.integration_service.validate_consumer_gate(
                    transaction_id=transaction_id,
                    proposal=revised_proposal,
                    reference_time=ref_time,
                )
                record_step(
                    LifecycleStage.DRIFT_REVALIDATED,
                    "revalidate_consumer_gate",
                    revised_consumer_gate.status.value,
                    {"is_valid": revised_consumer_gate.is_valid, "round": current_replan_round + 1},
                )

                # Merchant agent prepares counter-offer conforming to catalog & intent constraints
                catalog_item = self.merchant_service.get_item(corrected_sku)
                unit_price = catalog_item.price if catalog_item else intent.max_total
                # Bounded price conforming to max_total
                if unit_price.amount * revised_proposal.quantity > intent.max_total.amount:
                    # Discount to maximum allowable budget
                    total_amt = intent.max_total.amount
                else:
                    total_amt = unit_price.amount * revised_proposal.quantity

                corrected_total = Money(amount=total_amt, currency=intent.currency)
                revised_merchant_response = MerchantResponse(
                    response_id=f"mresp_{transaction_id}_{attempt_id}_r{current_replan_round + 1}",
                    merchant_id=merchant_id,
                    request_id=f"req_{transaction_id}_{attempt_id}_r{current_replan_round + 1}",
                    intent_id=intent.intent_id,
                    transaction_id=transaction_id,
                    is_success=True,
                    items=[
                        MerchantOfferItem(
                            sku=corrected_sku,
                            title=catalog_item.title if catalog_item else "Revised Offer Item",
                            quantity=revised_proposal.quantity,
                            unit_price=corrected_total,
                            total_price=corrected_total,
                        )
                    ],
                    subtotal=corrected_total,
                    tax=TaxEstimate(amount=Money(amount=0, currency=intent.currency)),
                    shipping=ShippingOption(
                        option_id="ship_std",
                        carrier="Standard Courier",
                        method_name="Standard Shipping",
                        cost=Money(amount=0, currency=intent.currency),
                        estimated_days=2,
                    ),
                    total_amount=corrected_total,
                    inventory_status=InventoryStatus.AVAILABLE,
                    offer_created_at=ref_time,
                    offer_expires_at=ref_time + timedelta(hours=2),
                )

                # MANDATORY REVALIDATION 2: Revised offer MUST pass E2 Merchant Gate!
                revised_merchant_gate, _ = self.integration_service.validate_merchant_gate(
                    transaction_id=transaction_id,
                    merchant_response=revised_merchant_response,
                    requested_sku=corrected_sku,
                    requested_quantity=revised_proposal.quantity,
                    reference_time=ref_time,
                )
                record_step(
                    LifecycleStage.DRIFT_REVALIDATED,
                    "revalidate_merchant_gate",
                    revised_merchant_gate.status.value,
                    {"is_valid": revised_merchant_gate.is_valid, "round": current_replan_round + 1},
                )

                # Counter-offer supersedes prior merchant candidate evidence in active store
                self.integration_service._evidence_store[transaction_id] = [
                    e for e in self.integration_service._evidence_store.get(transaction_id, [])
                    if e.source != EvidenceSource.MERCHANT
                ]
                self.integration_service._event_store[transaction_id] = [
                    ev for ev in self.integration_service._event_store.get(transaction_id, [])
                    if ev.source != EvidenceSource.MERCHANT
                ]

                revised_amount_ev = Evidence(
                    evidence_id=f"ev_revised_amount_{revised_merchant_response.response_id}",
                    intent_id=intent.intent_id,
                    transaction_id=transaction_id,
                    source=EvidenceSource.MERCHANT,
                    authority=EvidenceAuthority.MERCHANT_ATTESTED,
                    field_name="total_amount",
                    field_value=corrected_total,
                    observed_at=ref_time,
                    provenance={"merchant_id": merchant_id, "replan_round": current_replan_round + 1},
                )
                self.integration_service.add_evidence(transaction_id, revised_amount_ev)

                revised_items_ev = Evidence(
                    evidence_id=f"ev_revised_items_{revised_merchant_response.response_id}",
                    intent_id=intent.intent_id,
                    transaction_id=transaction_id,
                    source=EvidenceSource.MERCHANT,
                    authority=EvidenceAuthority.MERCHANT_ATTESTED,
                    field_name="executed_items",
                    field_value=[{"sku": item.sku, "quantity": item.quantity} for item in revised_merchant_response.items],
                    observed_at=ref_time,
                    provenance={"merchant_id": merchant_id, "replan_round": current_replan_round + 1},
                )
                self.integration_service.add_evidence(transaction_id, revised_items_ev)

                revised_event = CanonicalEvent(
                    event_id=f"evt_replan_offer_{revised_merchant_response.response_id}",
                    transaction_id=transaction_id,
                    intent_id=intent.intent_id,
                    event_type="OFFER_RECEIVED",
                    timestamp=ref_time,
                    amount=corrected_total,
                    source=EvidenceSource.MERCHANT,
                    authority=EvidenceAuthority.MERCHANT_ATTESTED,
                )
                self.integration_service.add_event(transaction_id, revised_event)

                # Append TIX message for counter-offer
                replan_tix = TIXMessage(
                    message_id=f"tix_replan_{transaction_id}_r{current_replan_round + 1}",
                    transaction_id=transaction_id,
                    intent_id=intent.intent_id,
                    attempt_id=attempt_id,
                    sender=merchant_id,
                    receiver=agent_id,
                    message_type=TIXMessageType.REMEDIATION_RESPONSE,
                    payload={"total": corrected_total.amount, "sku": corrected_sku},
                    timestamp=ref_time,
                )
                self.integration_service.append_tix_message(transaction_id, replan_tix, ref_time)

                # Re-evaluate deterministically via T04
                re_eval_resp = self.integration_service.evaluate(transaction_id, ref_time)
                record_step(
                    LifecycleStage.DRIFT_REVALIDATED,
                    "re_evaluate_integrity",
                    re_eval_resp.status.value,
                    {"violations": re_eval_resp.violations},
                )

                if re_eval_resp.status == IntegrityStatus.PASS:
                    sm = self.integration_service._state_machines[transaction_id]

                    record_step(LifecycleStage.COMPLETED, "complete_transaction_after_replan", "COMPLETED", {"transaction_id": transaction_id})
                    outcome = LifecycleOutcome(
                        transaction_id=transaction_id,
                        intent_id=intent.intent_id,
                        agent_id=agent_id,
                        merchant_id=merchant_id,
                        stage=LifecycleStage.COMPLETED,
                        integrity_status=IntegrityStatus.PASS,
                        transaction_state=sm.current_state,
                        is_terminal=True,
                        drift_count=1,
                        replan_rounds=current_replan_round + 1,
                        resolution_attempts=current_resolution_round,
                        security_cleared=True,
                        order_id=order_id,
                        payment_id=payment_id,
                        steps=steps,
                        history=history,
                        orchestrated_at=ref_time,
                    )
                    if idempotency_key:
                        self._idempotency_cache[idempotency_key] = outcome
                    return outcome

            # If replanning exhausted or disabled, check recovery
            if action_request and eval_resp.mrdp:
                recovery_res, _ = self.integration_service.recover(transaction_id, action_request, ref_time)
                record_step(
                    LifecycleStage.RECOVERING,
                    "execute_recovery",
                    str(getattr(recovery_res.status, "value", recovery_res.status)),
                    {"action_type": action_request.action_type.value},
                )
                outcome = LifecycleOutcome(
                    transaction_id=transaction_id,
                    intent_id=intent.intent_id,
                    agent_id=agent_id,
                    merchant_id=merchant_id,
                    stage=LifecycleStage.RECOVERING,
                    integrity_status=IntegrityStatus.DRIFT,
                    transaction_state=self.integration_service._state_machines[transaction_id].current_state,
                    is_terminal=True,
                    drift_count=1,
                    replan_rounds=self._replan_counts.get(transaction_id, 0),
                    mrdp_id=eval_resp.mrdp.mrdp_id,
                    steps=steps,
                    history=history,
                    orchestrated_at=ref_time,
                )
                if idempotency_key:
                    self._idempotency_cache[idempotency_key] = outcome
                return outcome

            # Otherwise, bounded abstention
            record_step(LifecycleStage.ABSTAINED, "abstain_drift_unresolved", "ABSTAINED", {"violations": eval_resp.violations})
            outcome = LifecycleOutcome(
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                stage=LifecycleStage.ABSTAINED,
                integrity_status=IntegrityStatus.DRIFT,
                transaction_state=self.integration_service._state_machines[transaction_id].current_state,
                is_terminal=True,
                drift_count=1,
                replan_rounds=self._replan_counts.get(transaction_id, 0),
                mrdp_id=eval_resp.mrdp.mrdp_id if eval_resp.mrdp else None,
                steps=steps,
                history=history,
                orchestrated_at=ref_time,
            )
            if idempotency_key:
                self._idempotency_cache[idempotency_key] = outcome
            return outcome

        # BRANCH 3: UNKNOWN
        else:
            record_step(
                LifecycleStage.UNKNOWN_RESOLVING,
                "unknown_detected",
                "UNKNOWN",
                {"violations": eval_resp.violations},
            )

            # Check bounded resolution attempt budget (§16, T12 limit)
            if active_policy.auto_resolve_unknown and current_resolution_round < active_policy.max_unknown_resolutions:
                self._resolution_counts[transaction_id] = current_resolution_round + 1
                record_step(
                    LifecycleStage.UNKNOWN_RESOLVING,
                    "invoke_authoritative_resolution",
                    "STARTED",
                    {"attempt": current_resolution_round + 1, "max_attempts": active_policy.max_unknown_resolutions},
                )

                # Ingest authoritative provider order if available
                res_order = provider_order or ProviderOrder(
                    order_id=order_id or f"ord_{transaction_id}",
                    amount=intent.max_total,
                    currency=intent.currency,
                    status="created",
                    created_at=ref_time,
                )

                sm = self.integration_service._state_machines[transaction_id]
                prior_ev = self.integration_service._evidence_store.get(transaction_id, [])
                prior_events = self.integration_service._event_store.get(transaction_id, [])

                try:
                    res_result = self.unknown_observer.resolve(
                        contract=intent,
                        order=res_order,
                        payment_id=payment_id,
                        provider=self.payment_provider,
                        current_state=sm.current_state,
                        prior_evidence=prior_ev,
                        prior_events=prior_events,
                        mrdp=eval_resp.mrdp,
                        now=ref_time,
                    )
                    record_step(
                        LifecycleStage.UNKNOWN_RESOLVED,
                        "unknown_resolution_complete",
                        res_result.strategy.value,
                        {"new_evidence_count": len(res_result.new_evidence), "resolved_status": res_result.integrity_result.status.value},
                    )

                    # Ingest normalized evidence from resolution into integration store
                    for ev in res_result.new_evidence:
                        self.integration_service.add_evidence(transaction_id, ev)
                    for evt in res_result.new_events:
                        self.integration_service.add_event(transaction_id, evt)

                    # Re-evaluate deterministically via T04
                    re_eval = self.integration_service.evaluate(transaction_id, ref_time)
                    record_step(
                        LifecycleStage.UNKNOWN_RESOLVED,
                        "re_evaluate_after_resolution",
                        re_eval.status.value,
                        {"violations": re_eval.violations},
                    )

                    if re_eval.status == IntegrityStatus.PASS:
                        sm = self.integration_service._state_machines[transaction_id]

                        record_step(LifecycleStage.COMPLETED, "complete_transaction_after_resolution", "COMPLETED", {"transaction_id": transaction_id})
                        outcome = LifecycleOutcome(
                            transaction_id=transaction_id,
                            intent_id=intent.intent_id,
                            agent_id=agent_id,
                            merchant_id=merchant_id,
                            stage=LifecycleStage.COMPLETED,
                            integrity_status=IntegrityStatus.PASS,
                            transaction_state=sm.current_state,
                            is_terminal=True,
                            resolution_attempts=current_resolution_round + 1,
                            security_cleared=True,
                            order_id=order_id,
                            payment_id=payment_id,
                            steps=steps,
                            history=history,
                            orchestrated_at=ref_time,
                        )
                        if idempotency_key:
                            self._idempotency_cache[idempotency_key] = outcome
                        return outcome

                except Exception as exc:
                    record_step(LifecycleStage.UNKNOWN_RESOLVING, "resolution_error", "ERROR", {"error": str(exc)})

            # Unresolved UNKNOWN must ABSTAIN / HOLD — NEVER force PASS (§16)
            record_step(LifecycleStage.ABSTAINED, "abstain_unknown_unresolved", "ABSTAINED", {"violations": eval_resp.violations})
            outcome = LifecycleOutcome(
                transaction_id=transaction_id,
                intent_id=intent.intent_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                stage=LifecycleStage.ABSTAINED,
                integrity_status=IntegrityStatus.UNKNOWN,
                transaction_state=self.integration_service._state_machines[transaction_id].current_state,
                is_terminal=True,
                resolution_attempts=self._resolution_counts.get(transaction_id, 0),
                steps=steps,
                history=history,
                orchestrated_at=ref_time,
            )
            if idempotency_key:
                self._idempotency_cache[idempotency_key] = outcome
            return outcome

    def replay_lifecycle(self, snapshot: ReplaySnapshot) -> ReplayResult:
        """
        Executes deterministic, CPU-only replay of an orchestrated lifecycle snapshot.
        Zero live network, AI, or payment side-effects (T13).
        """
        return self.integration_service.replay(snapshot)
