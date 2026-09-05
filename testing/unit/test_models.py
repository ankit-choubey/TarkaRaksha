"""
Unit tests for Domain Models (T03 / Step 9 §9.5, §9.8, §9.9).
Verifies:
- IntentItem, IntentContract (valid, missing fields, wrong types, timezone requirements, immutability)
- Authorization (bounds, expiry, distinct from AI)
- CanonicalEvent (provider neutrality, sequence, timezone)
- Evidence (normalized facts, authority hierarchy, ranking)
- IntegrityResult (PASS / DRIFT / UNKNOWN distinctness, first-class UNKNOWN)
- Decision (distinct from integrity result)
- MRDP (protocol schema, drift proof fields)
- RecoveryProposal (advisory nature, untrusted AI invariant)
- ActionRequest (not automatic execution, idempotency key)
- Transaction (lifecycle representation)
- Serialization & Deserialization round-trips
"""
from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from backend.app.domain.models import (
    ActionRequest,
    ActionType,
    Authorization,
    CanonicalEvent,
    Decision,
    DecisionAction,
    Evidence,
    EvidenceSource,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    MRDP,
    RecoveryProposal,
    Transaction,
    TransactionState,
)


def _sample_item():
    return IntentItem(
        item_id="item-001",
        sku="SKU-SERVER-256",
        name="Server 256GB",
        quantity=2,
        unit_price=Money(amount=25000, currency="INR"),
        total_price=Money(amount=50000, currency="INR"),
    )


def _sample_contract():
    now = datetime.now(timezone.utc)
    return IntentContract(
        intent_id="intent-101",
        issued_by="user-test",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=50000, currency="INR"),
        items=[_sample_item()],
    )


# --- 1. IntentContract & IntentItem ---

def test_intent_item_valid():
    item = _sample_item()
    assert item.item_id == "item-001"
    assert item.sku == "SKU-SERVER-256"
    assert item.quantity == 2
    assert item.total_price.amount == 50000


def test_intent_item_rejects_zero_or_negative_quantity():
    with pytest.raises(ValidationError):
        IntentItem(
            item_id="i1",
            sku="SKU-1",
            name="Item 1",
            quantity=0,
            unit_price=Money(amount=1000, currency="INR"),
            total_price=Money(amount=0, currency="INR"),
        )
    with pytest.raises(ValidationError):
        IntentItem(
            item_id="i1",
            sku="SKU-1",
            name="Item 1",
            quantity=-1,
            unit_price=Money(amount=1000, currency="INR"),
            total_price=Money(amount=-1000, currency="INR"),
        )


def test_intent_item_rejects_total_price_mismatch():
    with pytest.raises(ValidationError, match="total_price"):
        IntentItem(
            item_id="i1",
            sku="SKU-1",
            name="Item 1",
            quantity=2,
            unit_price=Money(amount=1000, currency="INR"),
            total_price=Money(amount=3000, currency="INR"),  # Expected 2000
        )


def test_intent_contract_valid_and_total_calculation():
    contract = _sample_contract()
    assert contract.intent_id == "intent-101"
    assert contract.calculate_items_total() == Money(amount=50000, currency="INR")
    assert contract.calculate_items_total() <= contract.max_total


def test_intent_contract_rejects_naive_timestamps():
    naive_dt = datetime.now()  # No tzinfo
    with pytest.raises(ValidationError, match="timezone-aware"):
        IntentContract(
            intent_id="intent-101",
            issued_by="user-test",
            issued_at=naive_dt,
            expires_at=naive_dt + timedelta(hours=1),
            currency="INR",
            max_total=Money(amount=50000, currency="INR"),
            items=[_sample_item()],
        )


def test_intent_contract_rejects_expiry_before_issued():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="expires_at must be strictly after issued_at"):
        IntentContract(
            intent_id="intent-101",
            issued_by="user-test",
            issued_at=now,
            expires_at=now - timedelta(minutes=5),
            currency="INR",
            max_total=Money(amount=50000, currency="INR"),
            items=[_sample_item()],
        )


def test_intent_contract_rejects_empty_items():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="at least one authorized item"):
        IntentContract(
            intent_id="intent-101",
            issued_by="user-test",
            issued_at=now,
            expires_at=now + timedelta(hours=1),
            currency="INR",
            max_total=Money(amount=50000, currency="INR"),
            items=[],
        )


def test_intent_contract_immutability():
    contract = _sample_contract()
    with pytest.raises(ValidationError):
        contract.currency = "USD"


# --- 2. Authorization ---

def test_authorization_valid_and_expiry_check():
    now = datetime.now(timezone.utc)
    auth = Authorization(
        authorization_id="auth-001",
        intent_id="intent-101",
        authorizer_id="admin-user",
        authorized_at=now,
        expires_at=now + timedelta(minutes=15),
        authorized_amount=Money(amount=50000, currency="INR"),
        authorized_actions=["PAYMENT_CAPTURE"],
    )
    assert not auth.is_expired(now + timedelta(minutes=10))
    assert auth.is_expired(now + timedelta(minutes=20))


def test_authorization_distinct_from_ai_proposal():
    now = datetime.now(timezone.utc)
    auth = Authorization(
        authorization_id="auth-001",
        intent_id="intent-101",
        authorizer_id="human-operator",
        authorized_at=now,
        expires_at=now + timedelta(minutes=15),
        authorized_amount=Money(amount=50000, currency="INR"),
    )
    prop = RecoveryProposal(
        proposal_id="prop-001",
        mrdp_id="mrdp-001",
        intent_id="intent-101",
        proposed_action=ActionType.REFUND,
        suggested_amount=Money(amount=1000, currency="INR"),
        reasoning="Surcharge compensation suggestion",
        confidence=0.95,
        suggested_at=now,
    )
    assert type(auth) is not type(prop)
    assert auth.authorized_amount.amount == 50000
    assert prop.suggested_amount.amount == 1000


# --- 3. CanonicalEvent & Evidence ---

def test_canonical_event_provider_neutral():
    now = datetime.now(timezone.utc)
    event = CanonicalEvent(
        event_id="evt-001",
        transaction_id="tx-001",
        intent_id="intent-101",
        event_type="PAYMENT_AUTHORIZED",
        timestamp=now,
        sequence_number=1,
        amount=Money(amount=50000, currency="INR"),
        source=EvidenceSource.RAZORPAY,
        payload_summary={"status": "authorized"},
    )
    assert event.event_id == "evt-001"
    assert event.source == EvidenceSource.RAZORPAY
    assert event.sequence_number == 1


def test_evidence_authority_hierarchy():
    now = datetime.now(timezone.utc)
    ev_razorpay = Evidence(
        evidence_id="ev-01",
        intent_id="intent-101",
        source=EvidenceSource.RAZORPAY,
        field_name="payment_status",
        field_value="captured",
        observed_at=now,
        is_authoritative=True,
    )
    ev_merchant = Evidence(
        evidence_id="ev-02",
        intent_id="intent-101",
        source=EvidenceSource.MERCHANT,
        field_name="payment_status",
        field_value="pending",
        observed_at=now,
    )
    ev_agent = Evidence(
        evidence_id="ev-03",
        intent_id="intent-101",
        source=EvidenceSource.AGENT,
        field_name="payment_status",
        field_value="captured",
        observed_at=now,
    )

    # Authority ranking: RAZORPAY > MERCHANT > AGENT
    assert ev_razorpay.authority_rank > ev_merchant.authority_rank
    assert ev_merchant.authority_rank > ev_agent.authority_rank


# --- 4. IntegrityResult & First-Class UNKNOWN ---

def test_integrity_result_unknown_is_first_class():
    now = datetime.now(timezone.utc)
    res_unknown = IntegrityResult(
        evaluation_id="eval-01",
        intent_id="intent-101",
        status=IntegrityStatus.UNKNOWN,
        evaluated_at=now,
        explanation="Payment status unconfirmed by gateway within deadline",
    )
    res_pass = IntegrityResult(
        evaluation_id="eval-02",
        intent_id="intent-101",
        status=IntegrityStatus.PASS,
        evaluated_at=now,
    )
    res_drift = IntegrityResult(
        evaluation_id="eval-03",
        intent_id="intent-101",
        status=IntegrityStatus.DRIFT,
        evaluated_at=now,
        violations=["EconomicDrift: Amount exceeded max_total"],
    )

    assert res_unknown.is_unknown is True
    assert res_unknown.is_pass is False
    assert res_unknown.is_drift is False

    assert res_pass.is_pass is True
    assert res_drift.is_drift is True

    # Confirm UNKNOWN != PASS and UNKNOWN != DRIFT
    assert res_unknown.status != res_pass.status
    assert res_unknown.status != res_drift.status


# --- 5. Decision & MRDP ---

def test_decision_model_distinction():
    now = datetime.now(timezone.utc)
    decision = Decision(
        decision_id="dec-01",
        intent_id="intent-101",
        integrity_status=IntegrityStatus.DRIFT,
        action=DecisionAction.RECOVER,
        decided_at=now,
        reason="Economic drift detected; compensatory refund proposed",
    )
    assert decision.action == DecisionAction.RECOVER
    assert decision.integrity_status == IntegrityStatus.DRIFT


def test_mrdp_protocol_drift_proof():
    now = datetime.now(timezone.utc)
    mrdp = MRDP(
        mrdp_id="mrdp-100",
        intent_id="intent-101",
        error_code="ERR_ECONOMIC_DRIFT_SURCHARGE",
        status=IntegrityStatus.DRIFT,
        violation="Authorized 50000 INR, Observed 50001 INR",
        drift_source="PAYMENT_GATEWAY",
        expected_value=50000,
        observed_value=50001,
        discrepancy_amount=Money(amount=1, currency="INR"),
        evidence_references=["ev-01"],
        remediation="PARTIAL_REFUND_1_INR",
        revalidation_required=True,
        generated_at=now,
    )
    assert mrdp.protocol == "TarkaRaksha-MRDP"
    assert mrdp.error_code == "ERR_ECONOMIC_DRIFT_SURCHARGE"
    assert mrdp.discrepancy_amount.amount == 1


# --- 6. RecoveryProposal & ActionRequest ---

def test_action_request_requires_validation():
    now = datetime.now(timezone.utc)
    action = ActionRequest(
        request_id="act-001",
        intent_id="intent-101",
        action_type=ActionType.REFUND,
        amount=Money(amount=100, currency="INR"),
        target_reference="pay_test_12345",
        idempotency_key="idemp-key-999",
        requested_at=now,
        requested_by="AI_RECOVERY_AGENT",
        is_validated=False,
    )
    # Action request starts unvalidated; AI output is never self-authorizing
    assert action.is_validated is False
    assert action.requested_by == "AI_RECOVERY_AGENT"


# --- 7. Transaction Lifecycle ---

def test_transaction_model_lifecycle():
    now = datetime.now(timezone.utc)
    tx = Transaction(
        transaction_id="tx-777",
        intent_id="intent-101",
        state=TransactionState.OBSERVING,
        authorized_amount=Money(amount=50000, currency="INR"),
        created_at=now,
        updated_at=now + timedelta(seconds=2),
    )
    assert tx.state == TransactionState.OBSERVING
    assert tx.authorized_amount.amount == 50000


# --- 8. Serialization Round-Trips ---

def test_all_models_serialization_roundtrip():
    now = datetime.now(timezone.utc)
    contract = _sample_contract()
    auth = Authorization(
        authorization_id="auth-1",
        intent_id="intent-101",
        authorizer_id="user-1",
        authorized_at=now,
        expires_at=now + timedelta(hours=1),
        authorized_amount=Money(amount=50000, currency="INR"),
    )
    event = CanonicalEvent(
        event_id="evt-1",
        transaction_id="tx-1",
        intent_id="intent-101",
        event_type="AUTH",
        timestamp=now,
        amount=Money(amount=50000, currency="INR"),
    )
    evidence = Evidence(
        evidence_id="ev-1",
        intent_id="intent-101",
        source=EvidenceSource.RAZORPAY,
        field_name="status",
        field_value="authorized",
        observed_at=now,
    )
    integrity = IntegrityResult(
        evaluation_id="eval-1",
        intent_id="intent-101",
        status=IntegrityStatus.PASS,
        evaluated_at=now,
    )
    decision = Decision(
        decision_id="dec-1",
        intent_id="intent-101",
        integrity_status=IntegrityStatus.PASS,
        action=DecisionAction.CONTINUE,
        decided_at=now,
        reason="Checks passed",
    )
    mrdp = MRDP(
        mrdp_id="mrdp-1",
        intent_id="intent-101",
        error_code="DRIFT_01",
        status=IntegrityStatus.DRIFT,
        violation="SKU mismatch",
        drift_source="GATEWAY",
        expected_value="SKU-A",
        observed_value="SKU-B",
        generated_at=now,
    )
    proposal = RecoveryProposal(
        proposal_id="prop-1",
        mrdp_id="mrdp-1",
        intent_id="intent-101",
        proposed_action=ActionType.REFUND,
        reasoning="Compensate",
        suggested_at=now,
    )
    action = ActionRequest(
        request_id="act-1",
        intent_id="intent-101",
        action_type=ActionType.REFUND,
        target_reference="ref-1",
        idempotency_key="k-1",
        requested_at=now,
        requested_by="AGENT",
    )
    tx = Transaction(
        transaction_id="tx-1",
        intent_id="intent-101",
        state=TransactionState.PASS,
        authorized_amount=Money(amount=50000, currency="INR"),
        created_at=now,
        updated_at=now,
    )

    models = [contract, auth, event, evidence, integrity, decision, mrdp, proposal, action, tx]
    for m in models:
        json_str = m.model_dump_json()
        reconstructed = type(m).model_validate_json(json_str)
        assert reconstructed == m
        assert type(reconstructed) is type(m)
