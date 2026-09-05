"""Unit and adversarial tests for E1 — Integration Boundary.

Covers:
- A. Valid Context Binding (intent + agent + merchant + transaction)
- B. Payment Linkage (order_id + payment_id bound to transaction)
- C. Agent Linkage Enforcement (wrong agent_id rejected)
- D. Intent Linkage Enforcement (wrong intent_id rejected)
- E. Merchant Linkage Enforcement (wrong merchant_id rejected)
- F. TIX Protocol Composition (valid TIX message enters validation path)
- G. Deterministic Integrity Composition (engine remains sole decision authority)
- H. Recovery Composition (bounded recovery rules preserved)
- I. Replay Composition (deterministic side-effect-free replay preserved)
- J. Critical Authority Tests (AI, Buyer, Merchant, TIX cannot declare PASS)
- K. Critical Cross-Context Defense (Transaction A vs Transaction B cross-contamination rejected)
- L. Failure & Unknown State Propagation (UNKNOWN preserved without guessing)
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingStatus,
    BindingVerificationOutcome,
    PaymentBindingClaim,
)
from backend.app.domain.buyer.contracts import BuyerTransactionProposal
from backend.app.domain.integration.contracts import (
    IntegrationBoundaryStage,
    IntegrationTransactionContext,
)
from backend.app.domain.merchant.contracts import (
    BuyerCommerceRequest,
    CatalogItem,
    InventoryRecord,
    InventoryStatus,
    MerchantOfferItem,
    MerchantResponse,
)
from backend.app.domain.models import (
    ActionRequest,
    ActionType,
    Authorization,
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceBundle,
    EvidenceSource,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    ProviderOrder,
    ProviderPayment,
    TransactionState,
)
from backend.app.domain.models.integrity import MRDP, MRDPErrorCode
from backend.app.domain.states import StateTransitionRecord
from backend.app.domain.tix.contracts import (
    TIXMessage,
    TIXMessageType,
    TIXParticipantRole,
)
from backend.app.services.integration import (
    ContextBindingMismatchError,
    IntegrationBoundaryError,
    IntegrationService,
)
from backend.app.services.replay.contracts import ReplaySnapshot, ReplayVerdict


@pytest.fixture
def base_intent() -> IntentContract:
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id="intent_test_e1_001",
        issued_by="buyer_e1_alice",
        items=[
            IntentItem(
                item_id="item_ssd_001",
                sku="SKU-SSD-1TB",
                name="1TB Portable SSD",
                quantity=1,
                unit_price=Money(amount=800000, currency="INR"),
                total_price=Money(amount=800000, currency="INR"),
            )
        ],
        max_total=Money(amount=800000, currency="INR"),
        currency="INR",
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=2),
    )


@pytest.fixture
def integration_service() -> IntegrationService:
    return IntegrationService()


# ==============================================================================
# 1. VALID CONTEXT BINDING & IDENTITY PRESERVATION
# ==============================================================================

def test_valid_context_initialization_and_intent_binding(integration_service, base_intent):
    """Verifies that an initial context is cleanly created and bound to an authorized intent."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    record = integration_service.create_context(
        transaction_id="tx_e1_001",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_tech_001",
        reference_time=ref_time,
    )

    assert record.context.transaction_id == "tx_e1_001"
    assert record.context.intent_id == base_intent.intent_id
    assert record.context.agent_id == "agent_buyer_001"
    assert record.context.merchant_id == "merchant_tech_001"
    assert record.stage == IntegrationBoundaryStage.INITIALIZED

    # Bind authorized intent
    bound_record = integration_service.bind_intent(
        transaction_id="tx_e1_001",
        intent=base_intent,
        reference_time=ref_time,
    )
    assert bound_record.stage == IntegrationBoundaryStage.INTENT_BOUND
    assert bound_record.intent == base_intent


def test_payment_linkage_preserves_7_tuple_binding(integration_service, base_intent):
    """Verifies that payment binding binds order_id and payment_id into context and registers I8 binding."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_e1_002",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_tech_001",
        reference_time=ref_time,
    )
    integration_service.bind_intent("tx_e1_002", base_intent, ref_time)

    claim = PaymentBindingClaim(
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_tech_001",
        transaction_id="tx_e1_002",
        order_id="order_e1_999",
        payment_id="pay_e1_888",
        attempt_id="att_1",
    )

    outcome, record = integration_service.bind_payment(
        transaction_id="tx_e1_002",
        order_id="order_e1_999",
        payment_id="pay_e1_888",
        claim=claim,
        reference_time=ref_time,
    )

    assert outcome.is_valid is True
    assert outcome.status == IntegrityStatus.PASS
    assert record.context.order_id == "order_e1_999"
    assert record.context.payment_id == "pay_e1_888"
    assert record.stage == IntegrationBoundaryStage.PAYMENT_BOUND


# ==============================================================================
# 2. CROSS-CONTEXT DEFENSE & LINKAGE ENFORCEMENT
# ==============================================================================

def test_wrong_agent_proposal_rejected(integration_service, base_intent):
    """A proposal bearing a mismatched agent_id must be rejected."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_e1_003",
        intent_id=base_intent.intent_id,
        agent_id="agent_legitimate_buyer",
        merchant_id="merchant_tech_001",
        reference_time=ref_time,
    )

    rogue_proposal = BuyerTransactionProposal(
        proposal_id="prop_rogue_001",
        buyer_agent_id="agent_attacker_impersonator",
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_003",
        sku="SKU-SSD-1TB",
        quantity=1,
        max_total=Money(amount=750000, currency="INR"),
    )

    with pytest.raises(ContextBindingMismatchError, match="Agent ID mismatch"):
        integration_service.process_buyer_proposal("tx_e1_003", rogue_proposal)


def test_wrong_intent_proposal_rejected(integration_service, base_intent):
    """A proposal bearing a mismatched intent_id must be rejected."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_e1_004",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_tech_001",
        reference_time=ref_time,
    )

    alien_proposal = BuyerTransactionProposal(
        proposal_id="prop_alien_001",
        buyer_agent_id="agent_buyer_001",
        intent_id="intent_alien_unrelated_999",
        transaction_id="tx_e1_004",
        sku="SKU-SSD-1TB",
        quantity=1,
        max_total=Money(amount=750000, currency="INR"),
    )

    with pytest.raises(ContextBindingMismatchError, match="Intent ID mismatch"):
        integration_service.process_buyer_proposal("tx_e1_004", alien_proposal)


def test_wrong_merchant_response_rejected(integration_service, base_intent):
    """A merchant response bearing a mismatched merchant_id must be rejected."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_e1_005",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_authorized_seller",
        reference_time=ref_time,
    )

    rogue_merchant_response = MerchantResponse(
        response_id="mresp_rogue_001",
        merchant_id="merchant_unauthorized_hijacker",
        request_id="req_rogue_001",
        is_success=True,
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_005",
        offer_created_at=ref_time,
        offer_expires_at=ref_time + timedelta(hours=1),
    )

    with pytest.raises(ContextBindingMismatchError, match="Merchant ID mismatch"):
        integration_service.process_merchant_response("tx_e1_005", rogue_merchant_response)


def test_cross_transaction_tamper_rejected(integration_service, base_intent):
    """Attempting to use Agent A from Transaction A in Transaction B must be strictly rejected."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_A",
        intent_id=base_intent.intent_id,
        agent_id="agent_alice",
        merchant_id="merchant_tech",
        reference_time=ref_time,
    )
    integration_service.create_context(
        transaction_id="tx_B",
        intent_id=base_intent.intent_id,
        agent_id="agent_bob",
        merchant_id="merchant_tech",
        reference_time=ref_time,
    )

    proposal_for_b_with_agent_a = BuyerTransactionProposal(
        proposal_id="prop_cross_001",
        buyer_agent_id="agent_alice",  # from tx_A
        intent_id=base_intent.intent_id,
        transaction_id="tx_B",
        sku="SKU-SSD-1TB",
        quantity=1,
        max_total=Money(amount=750000, currency="INR"),
    )

    with pytest.raises(ContextBindingMismatchError, match="Agent ID mismatch: expected agent_bob"):
        integration_service.process_buyer_proposal("tx_B", proposal_for_b_with_agent_a)


# ==============================================================================
# 3. CRITICAL AUTHORITY INVARIANTS
# ==============================================================================

def test_critical_authority_agents_and_tix_cannot_declare_pass(integration_service, base_intent):
    """
    Architectural Invariant:
    Neither Buyer Agent proposal, Merchant Agent offer, nor TIX message can declare PASS.
    Only the deterministic engine evaluation over authoritative evidence can yield PASS.
    """
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_e1_authority",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_tech_001",
        reference_time=ref_time,
    )
    integration_service.bind_intent("tx_e1_authority", base_intent, ref_time)

    # 1. Ingest buyer proposal
    proposal = BuyerTransactionProposal(
        proposal_id="prop_auth_001",
        buyer_agent_id="agent_buyer_001",
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_authority",
        sku="SKU-SSD-1TB",
        quantity=1,
        max_total=Money(amount=750000, currency="INR"),
    )
    rec1 = integration_service.process_buyer_proposal("tx_e1_authority", proposal)
    assert rec1.integrity_result is None

    # 2. Ingest merchant response
    m_resp = MerchantResponse(
        response_id="mresp_auth_001",
        merchant_id="merchant_tech_001",
        request_id="req_auth_001",
        is_success=True,
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_authority",
        offer_created_at=ref_time,
        offer_expires_at=ref_time + timedelta(hours=1),
    )
    rec2 = integration_service.process_merchant_response("tx_e1_authority", m_resp)
    assert rec2.integrity_result is None

    # 3. Ingest TIX message
    tix_msg = TIXMessage(
        message_id="tix_msg_001",
        transaction_id="tx_e1_authority",
        intent_id=base_intent.intent_id,
        attempt_id="att_1",
        sender="agent_buyer_001",
        receiver="tarkaraksha_core",
        message_type=TIXMessageType.INTENT,
        timestamp=ref_time,
        payload={"claim": "I declare this transaction PASS"},
    )
    outcome, rec3 = integration_service.append_tix_message("tx_e1_authority", tix_msg, ref_time)
    assert outcome.is_valid is True
    assert rec3.integrity_result is None  # Still NO PASS declared!

    # 4. Deterministic evaluation with NO authoritative payment evidence -> UNKNOWN
    eval_resp = integration_service.evaluate("tx_e1_authority", ref_time)
    assert eval_resp.status == IntegrityStatus.UNKNOWN
    assert eval_resp.state == TransactionState.UNKNOWN


# ==============================================================================
# 4. FAILURE & UNKNOWN STATE PROPAGATION
# ==============================================================================

def test_deterministic_drift_and_mrdp_generation(integration_service, base_intent):
    """
    Verifies that when an authoritative overcharge is observed, E1 integration
    propagates DRIFT and constructs an authoritative MRDP without faking success.
    """
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_e1_drift",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_tech_001",
        reference_time=ref_time,
    )
    integration_service.bind_intent("tx_e1_drift", base_intent, ref_time)

    # Add authoritative provider evidence showing price surge to ₹8,500 (limit is ₹8,000)
    drift_ev = Evidence(
        evidence_id="ev_provider_drift_001",
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_drift",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=850000, currency="INR"),
        observed_at=ref_time,
        is_authoritative=True,
    )
    integration_service.add_evidence("tx_e1_drift", drift_ev)

    eval_resp = integration_service.evaluate("tx_e1_drift", ref_time)
    assert eval_resp.status == IntegrityStatus.DRIFT
    assert eval_resp.state == TransactionState.DRIFT
    assert eval_resp.mrdp is not None
    assert eval_resp.mrdp.status == IntegrityStatus.DRIFT
    assert eval_resp.mrdp.error_code == MRDPErrorCode.ECONOMIC_AMOUNT_EXCEEDED.value


def test_clean_pass_evaluation(integration_service, base_intent):
    """
    Verifies that when matching authoritative evidence is present,
    the deterministic engine evaluates cleanly to PASS.
    """
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_e1_pass",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_tech_001",
        reference_time=ref_time,
    )
    integration_service.bind_intent("tx_e1_pass", base_intent, ref_time)

    # Valid matching payment evidence (₹7,500 <= ₹8,000 max)
    valid_amount_ev = Evidence(
        evidence_id="ev_provider_pass_001",
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_pass",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=750000, currency="INR"),
        observed_at=ref_time,
        is_authoritative=True,
    )
    valid_items_ev = Evidence(
        evidence_id="ev_provider_pass_002",
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_pass",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="executed_items",
        field_value=[{"sku": "SKU-SSD-1TB", "quantity": 1}],
        observed_at=ref_time,
        is_authoritative=True,
    )
    pass_event = CanonicalEvent(
        event_id="evt_pass_001",
        transaction_id="tx_e1_pass",
        intent_id=base_intent.intent_id,
        event_type="PAYMENT_CAPTURED",
        timestamp=ref_time + timedelta(minutes=1),
        sequence_number=1,
        source=EvidenceSource.RAZORPAY,
        amount=Money(amount=750000, currency="INR"),
    )
    integration_service.add_evidence("tx_e1_pass", valid_amount_ev)
    integration_service.add_evidence("tx_e1_pass", valid_items_ev)
    integration_service.add_event("tx_e1_pass", pass_event)

    eval_resp = integration_service.evaluate("tx_e1_pass", ref_time + timedelta(minutes=2))
    assert eval_resp.status == IntegrityStatus.PASS
    assert eval_resp.state == TransactionState.PASS
    assert eval_resp.mrdp is None


# ==============================================================================
# 5. RECOVERY & REPLAY COMPOSITION
# ==============================================================================

def test_recovery_composition_delegates_to_authoritative_executor(integration_service, base_intent):
    """Verifies that E1 delegates recovery to the existing T11 RecoveryExecutor."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    integration_service.create_context(
        transaction_id="tx_e1_rec",
        intent_id=base_intent.intent_id,
        agent_id="agent_buyer_001",
        merchant_id="merchant_tech_001",
        reference_time=ref_time,
    )
    integration_service.bind_intent("tx_e1_rec", base_intent, ref_time)

    # Induce drift
    drift_ev = Evidence(
        evidence_id="ev_drift_rec_001",
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_rec",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=850000, currency="INR"),
        observed_at=ref_time,
        is_authoritative=True,
    )
    integration_service.add_evidence("tx_e1_rec", drift_ev)
    integration_service.evaluate("tx_e1_rec", ref_time)

    # Execute recovery request
    action = ActionRequest(
        request_id="act_rec_001",
        intent_id=base_intent.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=50000, currency="INR"),
        target_reference="pay_mock_refund_001",
        idempotency_key="idem_key_rec_001",
        requested_at=ref_time,
        requested_by="OPERATOR",
    )

    rec_result, record = integration_service.recover("tx_e1_rec", action, ref_time)
    assert rec_result.status == "SUCCESS"
    assert record.stage == IntegrationBoundaryStage.RECOVERED
    assert record.recovery_result is not None


def test_replay_composition_delegates_to_pure_cpu_engine(integration_service, base_intent):
    """Verifies that E1 invokes T13 ReplayEngine purely over historical snapshot."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    # Valid evidence matching intent
    ev_amount = Evidence(
        evidence_id="ev_replay_001",
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_rep",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=750000, currency="INR"),
        observed_at=ref_time + timedelta(minutes=2),
        is_authoritative=True,
    )
    ev_items = Evidence(
        evidence_id="ev_replay_002",
        intent_id=base_intent.intent_id,
        transaction_id="tx_e1_rep",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="executed_items",
        field_value=[{"sku": "SKU-SSD-1TB", "quantity": 1}],
        observed_at=ref_time + timedelta(minutes=2),
        is_authoritative=True,
    )

    evt = CanonicalEvent(
        event_id="evt_replay_001",
        transaction_id="tx_e1_rep",
        intent_id=base_intent.intent_id,
        event_type="PAYMENT_CAPTURED",
        timestamp=ref_time + timedelta(minutes=1),
        sequence_number=1,
        source=EvidenceSource.RAZORPAY,
        amount=Money(amount=750000, currency="INR"),
    )

    pass_transitions = [
        StateTransitionRecord(
            transition_id="tr_rep_1",
            from_state=TransactionState.CREATED,
            to_state=TransactionState.EXECUTING,
            reason="Execution started",
            timestamp=ref_time + timedelta(seconds=10),
        ),
        StateTransitionRecord(
            transition_id="tr_rep_2",
            from_state=TransactionState.EXECUTING,
            to_state=TransactionState.OBSERVING,
            reason="Observing events",
            timestamp=ref_time + timedelta(seconds=20),
        ),
        StateTransitionRecord(
            transition_id="tr_rep_3",
            from_state=TransactionState.OBSERVING,
            to_state=TransactionState.VERIFYING,
            reason="Verifying integrity",
            timestamp=ref_time + timedelta(seconds=30),
        ),
        StateTransitionRecord(
            transition_id="tr_rep_4",
            from_state=TransactionState.VERIFYING,
            to_state=TransactionState.PASS,
            reason="Verification passed",
            timestamp=ref_time + timedelta(seconds=40),
            integrity_status=IntegrityStatus.PASS,
        ),
    ]

    rec_integrity = IntegrityResult(
        evaluation_id="eval_rec_001",
        intent_id=base_intent.intent_id,
        status=IntegrityStatus.PASS,
        evaluated_at=ref_time + timedelta(seconds=40),
        rule_results={
            "EconomicIntegrityRule": True,
            "SemanticIntegrityRule": True,
            "TemporalIntegrityRule": True,
        },
        violations=[],
        evidence_ids=["ev_replay_001", "ev_replay_002"],
    )

    snapshot = ReplaySnapshot(
        replay_id="rep_e1_001",
        transaction_id="tx_e1_rep",
        contract=base_intent,
        events=[evt],
        evidence=[ev_amount, ev_items],
        state_transitions=pass_transitions,
        recorded_integrity_result=rec_integrity,
        recorded_final_state=TransactionState.PASS,
        reference_time=ref_time + timedelta(seconds=40),
        rules_version="1.0.0",
    )

    replay_result = integration_service.replay(snapshot)
    assert replay_result.verdict == ReplayVerdict.MATCH
    assert replay_result.discrepancies == []


# ==============================================================================
# 6. APPLICATION-FACING API ENDPOINT TESTS
# ==============================================================================

def test_integration_api_create_and_fetch_context():
    """Verifies POST /api/v1/integration/context and GET /api/v1/integration/{id}."""
    client = TestClient(app)

    payload = {
        "transaction_id": "tx_api_001",
        "intent_id": "intent_api_001",
        "agent_id": "agent_buyer_001",
        "merchant_id": "merchant_tech_001",
    }
    create_res = client.post("/api/v1/integration/context", json=payload)
    assert create_res.status_code == 200
    data = create_res.json()
    assert data["context"]["transaction_id"] == "tx_api_001"
    assert data["stage"] == "INITIALIZED"
    assert data["context"]["intent_id"] == "intent_api_001"
    assert data["context"]["agent_id"] == "agent_buyer_001"

    # Fetch context
    fetch_res = client.get("/api/v1/integration/tx_api_001")
    assert fetch_res.status_code == 200
    fetch_data = fetch_res.json()
    assert fetch_data["context"]["transaction_id"] == "tx_api_001"
    assert fetch_data["stage"] == "INITIALIZED"


def test_integration_api_not_found():
    """Verifies that requesting a non-existent transaction context returns 404."""
    client = TestClient(app)
    res = client.get("/api/v1/integration/non_existent_tx_999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
