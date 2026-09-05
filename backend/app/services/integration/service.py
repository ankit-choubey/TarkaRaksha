"""
Integration Service for TarkaRaksha (E1).

Provides a single application-facing composition boundary around existing components:
- Buyer Agent (I5)
- Merchant Agent (I4)
- Intent & Authorizations (T03, T08)
- Transaction Lifecycle & State Machine (T05, T10)
- TIX Protocol (I6)
- Deterministic Integrity Engine (T04)
- Machine-Readable Drift Proof (MRDP, T07)
- Bounded Recovery Loop (T11)
- UNKNOWN Resolution (T12)
- Provider Integration (T09, Razorpay)
- Replay Engine (T13)
- 7-Tuple Binding Service (I8)
- Execution Safety / Kill Switch (I9)

Architectural Invariants:
- AI is advisory. Deterministic verification is authoritative.
- The Integration Service is purely an orchestrator / composition boundary;
  it never becomes a second business-logic layer, second decision engine, or second payment authority.
- No direct PASS declarations without deterministic engine evaluation.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingVerificationOutcome,
    PaymentBindingClaim,
)
from backend.app.domain.buyer.contracts import BuyerTransactionProposal
from backend.app.domain.integration.contracts import (
    IntegrationBoundaryStage,
    IntegrationEvaluationResponse,
    IntegrationExecutionRecord,
    IntegrationTransactionContext,
)
from backend.app.domain.merchant.contracts import BuyerCommerceRequest, MerchantResponse
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
from backend.app.domain.states.machine import TransactionStateMachine
from backend.app.domain.tix.contracts import (
    TIXMessage,
    TIXMessageType,
    TIXParticipantRole,
    TIXVerificationOutcome,
)
from backend.app.services.binding import TransactionBindingService
from backend.app.services.buyer.agent_service import BuyerAgentService
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.kill_switch import KillSwitchService
from backend.app.services.merchant.catalog_service import MerchantCatalogService
from backend.app.services.mrdp import build_mrdp
from backend.app.services.payment import PaymentProvider, RazorpayAdapter
from backend.app.services.recovery import (
    RecoveryExecutionResult,
    RecoveryExecutor,
    classify_recovery,
    revalidate_recovery,
    validate_action_request,
)
from backend.app.services.replay.contracts import ReplayResult, ReplaySnapshot
from backend.app.services.replay.engine import ReplayEngine
from backend.app.services.resolution import UnknownObserver, diagnose_unknown
from backend.app.services.tix import TIXExchangeService

logger = logging.getLogger(__name__)


class IntegrationBoundaryError(Exception):
    """Base exception for integration boundary violations."""
    pass


class ContextBindingMismatchError(IntegrationBoundaryError):
    """Raised when an entity attempts to attach to an incompatible transaction context."""
    pass


class IntegrationService:
    """
    Stable application-facing integration & composition boundary.
    Composes existing domain services without duplicating their authority.
    """

    def __init__(
        self,
        binding_service: Optional[TransactionBindingService] = None,
        kill_switch_service: Optional[KillSwitchService] = None,
        tix_service: Optional[TIXExchangeService] = None,
        merchant_service: Optional[MerchantCatalogService] = None,
        buyer_service: Optional[BuyerAgentService] = None,
        recovery_executor: Optional[RecoveryExecutor] = None,
        payment_provider: Optional[PaymentProvider] = None,
    ):
        self.binding_service = binding_service or TransactionBindingService()
        self.kill_switch_service = kill_switch_service or KillSwitchService()
        self.tix_service = tix_service or TIXExchangeService()
        self.merchant_service = merchant_service or MerchantCatalogService()
        self.buyer_service = buyer_service or BuyerAgentService()
        self.recovery_executor = recovery_executor or RecoveryExecutor()
        self.payment_provider = payment_provider or RazorpayAdapter()

        # In-memory registry of active integration transaction records
        self._records: Dict[str, IntegrationExecutionRecord] = {}
        self._state_machines: Dict[str, TransactionStateMachine] = {}
        self._evidence_store: Dict[str, List[Evidence]] = {}
        self._event_store: Dict[str, List[CanonicalEvent]] = {}

    def create_context(
        self,
        transaction_id: str,
        intent_id: str,
        agent_id: str,
        merchant_id: str,
        attempt_id: str = "att_1",
        metadata: Optional[Dict[str, Any]] = None,
        reference_time: Optional[datetime] = None,
    ) -> IntegrationExecutionRecord:
        """
        Creates and registers an initial IntegrationTransactionContext.
        Initializes the underlying authoritative T05 state machine and safety gate.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        context = IntegrationTransactionContext(
            transaction_id=transaction_id,
            intent_id=intent_id,
            agent_id=agent_id,
            merchant_id=merchant_id,
            attempt_id=attempt_id,
            created_at=ref_time,
            metadata=metadata or {},
        )

        sm = None
        self._state_machines[transaction_id] = sm
        self._evidence_store[transaction_id] = []
        self._event_store[transaction_id] = []

        record = IntegrationExecutionRecord(
            context=context,
            stage=IntegrationBoundaryStage.INITIALIZED,
            history=[f"{ref_time.isoformat()}: Context initialized with 4-tuple ({transaction_id}, {intent_id}, {agent_id}, {merchant_id})"],
            created_at=ref_time,
            updated_at=ref_time,
        )
        self._records[transaction_id] = record
        return record

    def bind_intent(
        self,
        transaction_id: str,
        intent: IntentContract,
        reference_time: Optional[datetime] = None,
    ) -> IntegrationExecutionRecord:
        """
        Binds an authorized IntentContract to the transaction context.
        Validates intent_id matches the context and initializes the state machine.
        """
        record = self._get_record(transaction_id)
        if intent.intent_id != record.context.intent_id:
            raise ContextBindingMismatchError(
                f"Intent ID mismatch: expected {record.context.intent_id}, received {intent.intent_id}"
            )

        ref_time = reference_time or datetime.now(timezone.utc)
        sm = TransactionStateMachine(
            transaction_id=transaction_id,
            intent=intent,
            created_at=ref_time,
        )
        self._state_machines[transaction_id] = sm

        record = record.model_copy(
            update={
                "intent": intent,
                "stage": IntegrationBoundaryStage.INTENT_BOUND,
                "history": record.history + [f"{ref_time.isoformat()}: Intent bound ({intent.intent_id})"],
                "updated_at": ref_time,
            }
        )
        self._records[transaction_id] = record
        return record

    def process_buyer_proposal(
        self,
        transaction_id: str,
        proposal: BuyerTransactionProposal,
        reference_time: Optional[datetime] = None,
    ) -> IntegrationExecutionRecord:
        """
        Ingests a Buyer Agent proposal and binds it to context.
        Enforces transaction_id, intent_id, and agent_id bindings.
        """
        record = self._get_record(transaction_id)
        if proposal.transaction_id != record.context.transaction_id:
            raise ContextBindingMismatchError(
                f"Transaction ID mismatch: expected {record.context.transaction_id}, received {proposal.transaction_id}"
            )
        if proposal.intent_id != record.context.intent_id:
            raise ContextBindingMismatchError(
                f"Intent ID mismatch: expected {record.context.intent_id}, received {proposal.intent_id}"
            )
        if proposal.buyer_agent_id != record.context.agent_id:
            raise ContextBindingMismatchError(
                f"Agent ID mismatch: expected {record.context.agent_id}, received {proposal.buyer_agent_id}"
            )

        ref_time = reference_time or datetime.now(timezone.utc)
        record = record.model_copy(
            update={
                "buyer_proposal": proposal,
                "history": record.history + [f"{ref_time.isoformat()}: Buyer proposal ingested ({proposal.proposal_id})"],
                "updated_at": ref_time,
            }
        )
        self._records[transaction_id] = record
        return record

    def process_merchant_response(
        self,
        transaction_id: str,
        merchant_response: MerchantResponse,
        reference_time: Optional[datetime] = None,
    ) -> IntegrationExecutionRecord:
        """
        Ingests a Merchant Agent response and binds it to context.
        Validates merchant identity against context.
        """
        record = self._get_record(transaction_id)
        if merchant_response.merchant_id != record.context.merchant_id:
            raise ContextBindingMismatchError(
                f"Merchant ID mismatch: expected {record.context.merchant_id}, received {merchant_response.merchant_id}"
            )

        ref_time = reference_time or datetime.now(timezone.utc)
        record = record.model_copy(
            update={
                "merchant_response": merchant_response,
                "stage": IntegrationBoundaryStage.OFFER_RECEIVED,
                "history": record.history + [f"{ref_time.isoformat()}: Merchant response ingested ({merchant_response.merchant_id})"],
                "updated_at": ref_time,
            }
        )
        self._records[transaction_id] = record
        return record

    def append_tix_message(
        self,
        transaction_id: str,
        message: TIXMessage,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[TIXVerificationOutcome, IntegrationExecutionRecord]:
        """
        Passes a TIX message through the existing TIXExchangeService.
        Validates cryptographic hash chaining, roles, and bindings.
        """
        record = self._get_record(transaction_id)
        outcome, hashed_msg = self.tix_service.append_and_verify(
            message=message,
            expected_intent_id=record.context.intent_id,
            expected_attempt_id=record.context.attempt_id,
            reference_time=reference_time,
        )

        ref_time = reference_time or datetime.now(timezone.utc)
        if not outcome.is_valid or hashed_msg is None:
            return outcome, record

        updated_messages = list(record.tix_messages) + [hashed_msg]
        record = record.model_copy(
            update={
                "tix_messages": updated_messages,
                "stage": IntegrationBoundaryStage.TIX_COMMITTED,
                "history": record.history + [f"{ref_time.isoformat()}: TIX message appended ({message.message_type})"],
                "updated_at": ref_time,
            }
        )
        self._records[transaction_id] = record
        return outcome, record

    def add_evidence(
        self,
        transaction_id: str,
        evidence: Evidence,
    ) -> None:
        """Adds an evidence record to the transaction evidence store."""
        self._get_record(transaction_id)
        self._evidence_store[transaction_id].append(evidence)

    def add_event(
        self,
        transaction_id: str,
        event: CanonicalEvent,
    ) -> None:
        """Adds a canonical event to the transaction event store."""
        self._get_record(transaction_id)
        self._event_store[transaction_id].append(event)

    def evaluate(
        self,
        transaction_id: str,
        reference_time: Optional[datetime] = None,
    ) -> IntegrationEvaluationResponse:
        """
        Evaluates integrity using the authoritative T04 deterministic engine.
        Does NOT decide independently. Delegates strictly to evaluate_integrity.
        """
        record = self._get_record(transaction_id)
        if not record.intent:
            raise IntegrationBoundaryError("Cannot evaluate transaction without bound IntentContract")

        ref_time = reference_time or datetime.now(timezone.utc)
        evidence_list = self._evidence_store.get(transaction_id, [])
        event_list = self._event_store.get(transaction_id, [])
        bundle = EvidenceBundle(
            bundle_id=f"bundle_{transaction_id}_{ref_time.strftime('%Y%m%d%H%M%S')}",
            intent_id=record.context.intent_id,
            transaction_id=transaction_id,
            created_at=ref_time,
            records=evidence_list,
            events=event_list,
        )

        # Authoritative T04 evaluation
        integrity_result = evaluate_integrity(
            contract=record.intent,
            evidence_list=evidence_list,
            events=event_list,
            reference_time=ref_time,
        )

        # Update authoritative state machine
        sm = self._state_machines[transaction_id]
        if sm.current_state == TransactionState.CREATED:
            sm.transition_to(to_state=TransactionState.EXECUTING, reason="execution_started", timestamp=ref_time)
        if sm.current_state == TransactionState.EXECUTING:
            sm.transition_to(to_state=TransactionState.OBSERVING, reason="observing_evidence", timestamp=ref_time)
        if sm.current_state == TransactionState.OBSERVING:
            sm.transition_to(to_state=TransactionState.VERIFYING, reason="integration_eval_start", timestamp=ref_time)

        mrdp_obj = None
        if integrity_result.status == IntegrityStatus.PASS:
            sm.transition_to(to_state=TransactionState.PASS, reason="evaluation_pass", timestamp=ref_time, integrity_status=IntegrityStatus.PASS)
        elif integrity_result.status == IntegrityStatus.DRIFT:
            sm.transition_to(to_state=TransactionState.DRIFT, reason="evaluation_drift", timestamp=ref_time, integrity_status=IntegrityStatus.DRIFT)
            # Build authoritative MRDP proof
            mrdp_obj = build_mrdp(
                contract=record.intent,
                integrity_result=integrity_result,
                evidence_bundle=bundle,
                generated_at=ref_time,
            )
        else:
            sm.transition_to(to_state=TransactionState.UNKNOWN, reason="evaluation_unknown", timestamp=ref_time, integrity_status=IntegrityStatus.UNKNOWN)

        record = record.model_copy(
            update={
                "integrity_result": integrity_result,
                "mrdp": mrdp_obj,
                "stage": IntegrationBoundaryStage.EVALUATED,
                "history": record.history + [f"{ref_time.isoformat()}: Deterministic evaluation -> {integrity_result.status.value}"],
                "updated_at": ref_time,
            }
        )
        self._records[transaction_id] = record

        return IntegrationEvaluationResponse(
            transaction_id=transaction_id,
            status=integrity_result.status,
            state=sm.current_state,
            rule_results=integrity_result.rule_results,
            violations=integrity_result.violations,
            evidence_count=len(evidence_list),
            mrdp=mrdp_obj,
            evaluated_at=ref_time,
        )

    def bind_payment(
        self,
        transaction_id: str,
        order_id: str,
        payment_id: str,
        claim: PaymentBindingClaim,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[BindingVerificationOutcome, IntegrationExecutionRecord]:
        """
        Binds order_id and payment_id to context and verifies via authoritative I8 binding service.
        """
        record = self._get_record(transaction_id)
        ref_time = reference_time or datetime.now(timezone.utc)

        # Update context with order_id and payment_id
        updated_context = record.context.with_order(order_id).with_payment(payment_id)

        # Register binding in authoritative I8 service
        self.binding_service.register_binding(
            intent_id=record.context.intent_id,
            agent_id=record.context.agent_id,
            merchant_id=record.context.merchant_id,
            transaction_id=transaction_id,
            order_id=order_id,
            attempt_id=record.context.attempt_id,
            created_at=ref_time,
        )

        # Verify claim
        outcome = self.binding_service.verify_transaction_binding(
            claim=claim,
            reference_time=ref_time,
        )

        # Add outcome to evidence store
        ev = outcome.to_evidence(
            intent_id=record.context.intent_id,
            transaction_id=transaction_id,
        )
        self._evidence_store[transaction_id].append(ev)

        record = record.model_copy(
            update={
                "context": updated_context,
                "binding_outcome": outcome,
                "stage": IntegrationBoundaryStage.PAYMENT_BOUND,
                "history": record.history + [f"{ref_time.isoformat()}: Payment bound ({order_id}, {payment_id}) -> is_valid={outcome.is_valid}"],
                "updated_at": ref_time,
            }
        )
        self._records[transaction_id] = record
        return outcome, record

    def recover(
        self,
        transaction_id: str,
        action_request: ActionRequest,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[RecoveryExecutionResult, IntegrationExecutionRecord]:
        """
        Executes bounded compensatory recovery via the authoritative T11 recovery executor.
        """
        record = self._get_record(transaction_id)
        if not record.mrdp:
            raise IntegrationBoundaryError("Cannot recover without Machine-Readable Drift Proof (MRDP)")

        ref_time = reference_time or datetime.now(timezone.utc)
        sm = self._state_machines[transaction_id]

        result = self.recovery_executor.execute(
            action_request=action_request,
            contract=record.intent,
            provider=self.payment_provider,
            current_state=sm.current_state,
            mrdp=record.mrdp,
            now=ref_time,
        )

        if sm.current_state == TransactionState.DRIFT:
            sm.transition_to(to_state=TransactionState.RECOVERING, reason="integration_recovery_start", timestamp=ref_time)

        record = record.model_copy(
            update={
                "recovery_result": result,
                "stage": IntegrationBoundaryStage.RECOVERED,
                "history": record.history + [f"{ref_time.isoformat()}: Recovery executed -> {result.status}"],
                "updated_at": ref_time,
            }
        )
        self._records[transaction_id] = record
        return result, record

    def replay(
        self,
        snapshot: ReplaySnapshot,
    ) -> ReplayResult:
        """
        Executes deterministic, CPU-only replay via authoritative T13 ReplayEngine.
        Zero live network or provider calls.
        """
        return ReplayEngine.replay(snapshot)

    def get_record(self, transaction_id: str) -> Optional[IntegrationExecutionRecord]:
        """Retrieves an execution record by transaction_id."""
        return self._records.get(transaction_id)

    def _get_record(self, transaction_id: str) -> IntegrationExecutionRecord:
        """Internal helper to retrieve record or raise."""
        record = self._records.get(transaction_id)
        if not record:
            raise IntegrationBoundaryError(f"Transaction context '{transaction_id}' not found")
        return record
