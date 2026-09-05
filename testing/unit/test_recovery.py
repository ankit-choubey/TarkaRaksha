"""
Unit Test Suite for T11: Recovery Loop.
Testing reference: brain/TarkaRaksha_TESTING.md, Execution §7.41-§7.55, Prompt T11.

Covers:
1. Recoverable DRIFT classification (economic overcharge discrepancy)
2. Non-recoverable DRIFT classification (semantic unauthorized SKU/quantity)
3. UNKNOWN remains UNKNOWN without sufficient evidence
4. Attempt bound enforcement in policy (escalates to ABSTAIN)
5. Temporal safety in policy (expired intent escalates to ABSTAIN)
6. ActionRequest deterministic safety validation
7. ActionRequest rejection of forbidden CAPTURE action
8. ActionRequest rejection of amount exceeding authorized max_total
9. ActionRequest rejection of amount exceeding detected MRDP discrepancy
10. ActionRequest rejection of invalid state transitions
11. Bounded recovery executor: refund execution produces canonical evidence and events
12. Recovery idempotency: duplicate idempotency key returns cached result
13. Recovery attempt bounds: 3 attempts allowed, attempt 4 raises RecoveryExhaustedError
14. Deterministic revalidation: compensatory refund nets out overcharge -> PASS
15. Deterministic revalidation: insufficient refund -> still DRIFT
16. Full transaction service recovery lifecycle: DRIFT -> RECOVERING -> REVALIDATING -> PASS
17. Full transaction service non-recoverable recovery -> ABSTAIN
18. FastAPI REST endpoint: POST /api/v1/transaction/recover
"""
from datetime import datetime, timedelta, timezone
import hashlib
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.models import (
    ActionRequest,
    ActionType,
    CanonicalEvent,
    CompleteTransactionRequest,
    CreateTransactionRequest,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityResult,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    MRDP,
    MRDPErrorCode,
    RecoverTransactionRequest,
    TransactionState,
)
from backend.app.domain.models.payment import ProviderPayment
from backend.app.domain.states import TransactionStateMachine
from backend.app.main import app, get_payment_provider, get_transaction_service
from backend.app.services.payment import FakePaymentProvider, compute_payment_signature
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
from backend.app.services.transaction_service import TransactionService


# ==============================================================================
# FIXTURES & HELPERS
# ==============================================================================

TEST_SECRET = "test_secret_recovery_t11_45678"


def make_test_intent(
    intent_id: str = "intent_rec_001",
    max_amount_paise: int = 5000000,
    currency: str = "INR",
    sku: str = "SERVER-256GB",
    quantity: int = 1,
    expires_in_hours: int = 24,
) -> IntentContract:
    now = datetime.now(timezone.utc)
    return IntentContract(
        intent_id=intent_id,
        issued_by="user_test",
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=expires_in_hours),
        currency=currency,
        max_total=Money(amount=max_amount_paise, currency=currency),
        items=[
            IntentItem(
                item_id=f"item_{intent_id}",
                sku=sku,
                name=f"Test Product {sku}",
                quantity=quantity,
                unit_price=Money(amount=max_amount_paise // quantity, currency=currency),
                total_price=Money(amount=max_amount_paise, currency=currency),
            )
        ],
    )


def make_economic_drift_mrdp(
    contract: IntentContract,
    captured_paise: int,
) -> MRDP:
    overcharge_paise = captured_paise - contract.max_total.amount
    now = datetime.now(timezone.utc)
    return MRDP(
        protocol="TarkaRaksha-MRDP",
        version="1.0.0",
        mrdp_id=f"mrdp_{contract.intent_id}",
        intent_id=contract.intent_id,
        error_code=MRDPErrorCode.ECONOMIC_AMOUNT_EXCEEDED.value,
        status=IntegrityStatus.DRIFT,
        violation=f"Captured amount {captured_paise} exceeds authorized max_total {contract.max_total.amount}",
        drift_source="RAZORPAY",
        expected_value={"max_total": contract.max_total.amount},
        observed_value={"captured_amount": captured_paise},
        discrepancy_amount=Money(amount=overcharge_paise, currency=contract.currency),
        remediation=f"Refund {overcharge_paise} paise to restore economic invariant",
        revalidation_required=True,
        evidence_references=[f"ev_{contract.intent_id}_captured"],
        generated_at=now,
        proof_digest="test_digest_123",
    )


# ==============================================================================
# 1. RECOVERY POLICY & CLASSIFICATION TESTS
# ==============================================================================

def test_classify_recovery_recoverable_economic_drift():
    contract = make_test_intent(max_amount_paise=5000000)
    mrdp = make_economic_drift_mrdp(contract, captured_paise=5500000)
    integrity_result = IntegrityResult(
        evaluation_id="eval_001",
        intent_id=contract.intent_id,
        status=IntegrityStatus.DRIFT,
        evaluated_at=datetime.now(timezone.utc),
        rule_results={"economic": False, "semantic": True, "temporal": True},
        violations=["Captured amount exceeds authorized max_total"],
        evidence_ids=[],
        confidence_score=1.0,
    )

    classification = classify_recovery(
        contract=contract,
        integrity_result=integrity_result,
        mrdp=mrdp,
    )

    assert classification.status == RecoverabilityStatus.RECOVERABLE
    assert classification.is_recoverable is True
    assert classification.recommended_action == ActionType.REFUND
    assert classification.max_allowed_amount == Money(amount=500000, currency="INR")


def test_classify_recovery_non_recoverable_semantic_drift():
    contract = make_test_intent(sku="SERVER-256GB")
    integrity_result = IntegrityResult(
        evaluation_id="eval_002",
        intent_id=contract.intent_id,
        status=IntegrityStatus.DRIFT,
        evaluated_at=datetime.now(timezone.utc),
        rule_results={"economic": True, "semantic": False, "temporal": True},
        violations=["UnauthorizedSKU: observed SKU GPU-H100 not in authorized items"],
        evidence_ids=[],
        confidence_score=1.0,
    )

    classification = classify_recovery(
        contract=contract,
        integrity_result=integrity_result,
    )

    assert classification.status == RecoverabilityStatus.NON_RECOVERABLE
    assert classification.is_recoverable is False
    assert classification.recommended_action == ActionType.CANCEL


def test_classify_recovery_unknown_missing_evidence():
    contract = make_test_intent()
    integrity_result = IntegrityResult(
        evaluation_id="eval_003",
        intent_id=contract.intent_id,
        status=IntegrityStatus.UNKNOWN,
        evaluated_at=datetime.now(timezone.utc),
        rule_results={"economic": False, "semantic": False, "temporal": False},
        violations=["Payment state could not be resolved from gateway"],
        evidence_ids=[],
        confidence_score=0.0,
        explanation="Missing authoritative gateway evidence",
    )

    classification = classify_recovery(
        contract=contract,
        integrity_result=integrity_result,
    )

    assert classification.status == RecoverabilityStatus.UNKNOWN
    assert classification.is_recoverable is True
    assert classification.recommended_action == ActionType.NOTIFY


def test_classify_recovery_attempt_budget_exceeded():
    contract = make_test_intent()
    integrity_result = IntegrityResult(
        evaluation_id="eval_004",
        intent_id=contract.intent_id,
        status=IntegrityStatus.DRIFT,
        evaluated_at=datetime.now(timezone.utc),
        rule_results={"economic": False, "semantic": True, "temporal": True},
        violations=["Economic overcharge"],
        evidence_ids=[],
        confidence_score=1.0,
    )

    # Attempt 3 is the limit, attempt 3 (current_attempt >= MAX_RECOVERY_ATTEMPTS) must escalate to ABSTAIN
    classification = classify_recovery(
        contract=contract,
        integrity_result=integrity_result,
        current_attempt=MAX_RECOVERY_ATTEMPTS,
    )

    assert classification.status == RecoverabilityStatus.ABSTAIN
    assert classification.is_recoverable is False
    assert "limit" in classification.reason.lower()


def test_classify_recovery_expired_intent_abstains():
    # Expired intent
    now = datetime.now(timezone.utc)
    contract = IntentContract(
        intent_id="intent_expired",
        issued_by="user_test",
        issued_at=now - timedelta(days=2),
        expires_at=now - timedelta(days=1),
        currency="INR",
        max_total=Money(amount=100000, currency="INR"),
        items=[
            IntentItem(
                item_id="item_exp_1",
                sku="SERVER-256GB",
                name="Server",
                quantity=1,
                unit_price=Money(amount=100000, currency="INR"),
                total_price=Money(amount=100000, currency="INR"),
            )
        ],
    )
    integrity_result = IntegrityResult(
        evaluation_id="eval_005",
        intent_id=contract.intent_id,
        status=IntegrityStatus.DRIFT,
        evaluated_at=now,
        rule_results={},
        violations=["Overcharge"],
        evidence_ids=[],
        confidence_score=1.0,
    )

    classification = classify_recovery(
        contract=contract,
        integrity_result=integrity_result,
        reference_time=now,
    )

    assert classification.status == RecoverabilityStatus.ABSTAIN
    assert classification.is_recoverable is False
    assert "expired" in classification.reason.lower()


# ==============================================================================
# 2. ACTION REQUEST VALIDATION TESTS
# ==============================================================================

def test_validate_action_request_valid_refund():
    contract = make_test_intent(max_amount_paise=5000000)
    mrdp = make_economic_drift_mrdp(contract, captured_paise=5500000)
    action_req = ActionRequest(
        request_id="act_001",
        intent_id=contract.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=500000, currency="INR"),
        target_reference="pay_12345",
        idempotency_key="idemp_001",
        requested_at=datetime.now(timezone.utc),
        requested_by="TEST",
    )

    validated = validate_action_request(
        action_request=action_req,
        contract=contract,
        mrdp=mrdp,
        current_state=TransactionState.DRIFT,
    )

    assert validated.is_validated is True
    assert validated.action_type == ActionType.REFUND
    assert validated.amount == Money(amount=500000, currency="INR")


def test_validate_action_request_strictly_forbids_capture():
    contract = make_test_intent()
    action_req = ActionRequest(
        request_id="act_capture",
        intent_id=contract.intent_id,
        action_type=ActionType.CAPTURE,
        amount=Money(amount=100000, currency="INR"),
        target_reference="pay_123",
        idempotency_key="idemp_cap",
        requested_at=datetime.now(timezone.utc),
        requested_by="ATTACKER",
    )

    with pytest.raises(UnsafeActionRequestError, match="CAPTURE is strictly forbidden"):
        validate_action_request(
            action_request=action_req,
            contract=contract,
            current_state=TransactionState.DRIFT,
        )


def test_validate_action_request_rejects_amount_exceeding_max_total():
    contract = make_test_intent(max_amount_paise=5000000)
    action_req = ActionRequest(
        request_id="act_excess",
        intent_id=contract.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=6000000, currency="INR"),  # Exceeds max_total
        target_reference="pay_123",
        idempotency_key="idemp_excess",
        requested_at=datetime.now(timezone.utc),
        requested_by="TEST",
    )

    with pytest.raises(UnsafeActionRequestError, match="exceeds authorized contract max_total"):
        validate_action_request(
            action_request=action_req,
            contract=contract,
            current_state=TransactionState.DRIFT,
        )


def test_validate_action_request_rejects_amount_exceeding_mrdp_discrepancy():
    contract = make_test_intent(max_amount_paise=5000000)
    mrdp = make_economic_drift_mrdp(contract, captured_paise=5500000)  # discrepancy is 500,000 paise
    action_req = ActionRequest(
        request_id="act_excess_discrepancy",
        intent_id=contract.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=600000, currency="INR"),  # Exceeds discrepancy of 500,000
        target_reference="pay_123",
        idempotency_key="idemp_excess_disc",
        requested_at=datetime.now(timezone.utc),
        requested_by="TEST",
    )

    with pytest.raises(UnsafeActionRequestError, match="exceeds detected MRDP discrepancy"):
        validate_action_request(
            action_request=action_req,
            contract=contract,
            mrdp=mrdp,
            current_state=TransactionState.DRIFT,
        )


def test_validate_action_request_rejects_illegal_state():
    contract = make_test_intent()
    action_req = ActionRequest(
        request_id="act_illegal_state",
        intent_id=contract.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=10000, currency="INR"),
        target_reference="pay_123",
        idempotency_key="idemp_ill",
        requested_at=datetime.now(timezone.utc),
        requested_by="TEST",
    )

    # Illegal state: CREATED
    with pytest.raises(InvalidRecoveryStateError, match="Cannot initiate or execute recovery from lifecycle state 'CREATED'"):
        validate_action_request(
            action_request=action_req,
            contract=contract,
            current_state=TransactionState.CREATED,
        )


# ==============================================================================
# 3. RECOVERY EXECUTOR & IDEMPOTENCY TESTS
# ==============================================================================

def test_recovery_executor_executes_refund_and_produces_evidence():
    executor = RecoveryExecutor()
    contract = make_test_intent(max_amount_paise=5000000)
    provider = FakePaymentProvider(mock_secret=TEST_SECRET)
    mrdp = make_economic_drift_mrdp(contract, captured_paise=5500000)

    action_req = ActionRequest(
        request_id="act_exec_001",
        intent_id=contract.intent_id,
        action_type=ActionType.REFUND,
        amount=Money(amount=500000, currency="INR"),
        target_reference="pay_target_123",
        idempotency_key="idemp_exec_001",
        requested_at=datetime.now(timezone.utc),
        requested_by="CONTROL_PLANE",
    )

    result = executor.execute(
        action_request=action_req,
        contract=contract,
        provider=provider,
        current_state=TransactionState.DRIFT,
        mrdp=mrdp,
    )

    assert result.status == "SUCCESS"
    assert result.is_idempotent_replay is False
    assert len(result.evidence) == 1
    assert result.evidence[0].field_name == "refund_amount"
    assert result.evidence[0].field_value == Money(amount=500000, currency="INR")
    assert result.evidence[0].authority == EvidenceAuthority.AUTHORITATIVE

    assert len(result.events) == 1
    assert result.events[0].event_type == "payment.refunded"
    assert result.events[0].amount == Money(amount=500000, currency="INR")


def test_recovery_executor_idempotency_duplicate_replay():
    executor = RecoveryExecutor()
    contract = make_test_intent()
    provider = FakePaymentProvider(mock_secret=TEST_SECRET)
    action_req = ActionRequest(
        request_id="act_exec_dup",
        intent_id=contract.intent_id,
        action_type=ActionType.NOTIFY,
        target_reference="order_123",
        idempotency_key="idemp_duplicate_key_42",
        requested_at=datetime.now(timezone.utc),
        requested_by="TEST",
    )

    # First execution
    res1 = executor.execute(
        action_request=action_req,
        contract=contract,
        provider=provider,
        current_state=TransactionState.DRIFT,
    )
    assert res1.is_idempotent_replay is False

    # Second execution with same idempotency key
    res2 = executor.execute(
        action_request=action_req,
        contract=contract,
        provider=provider,
        current_state=TransactionState.DRIFT,
    )
    assert res2.is_idempotent_replay is True
    assert res2.status == "DUPLICATE"
    assert res2.details["original_execution_id"] == res1.execution_id


def test_recovery_executor_attempt_budget_exhaustion():
    executor = RecoveryExecutor()
    contract = make_test_intent()
    provider = FakePaymentProvider(mock_secret=TEST_SECRET)

    # Execute MAX_RECOVERY_ATTEMPTS (3)
    for i in range(MAX_RECOVERY_ATTEMPTS):
        req = ActionRequest(
            request_id=f"act_budget_{i}",
            intent_id=contract.intent_id,
            action_type=ActionType.NOTIFY,
            target_reference="ord_123",
            idempotency_key=f"idemp_distinct_{i}",
            requested_at=datetime.now(timezone.utc),
            requested_by="TEST",
        )
        executor.execute(
            action_request=req,
            contract=contract,
            provider=provider,
            current_state=TransactionState.DRIFT,
        )

    # Attempt 4 must raise RecoveryExhaustedError
    req_4 = ActionRequest(
        request_id="act_budget_exhausted",
        intent_id=contract.intent_id,
        action_type=ActionType.NOTIFY,
        target_reference="ord_123",
        idempotency_key="idemp_budget_exhausted",
        requested_at=datetime.now(timezone.utc),
        requested_by="TEST",
    )
    with pytest.raises(RecoveryExhaustedError, match="Recovery attempts limit"):
        executor.execute(
            action_request=req_4,
            contract=contract,
            provider=provider,
            current_state=TransactionState.DRIFT,
        )


# ==============================================================================
# 4. DETERMINISTIC REVALIDATION TESTS
# ==============================================================================

def test_revalidate_recovery_restores_pass_after_refund():
    contract = make_test_intent(max_amount_paise=5000000)
    now = datetime.now(timezone.utc)

    # Prior evidence: overcharge of 55,000 INR (5,500,000 paise)
    prior_evidence = [
        Evidence(
            evidence_id="ev_orig_amount",
            intent_id=contract.intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="total_amount",
            field_value=Money(amount=5500000, currency="INR"),
            observed_at=now,
            raw_reference="pay_123",
        ),
        Evidence(
            evidence_id="ev_orig_items",
            intent_id=contract.intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="executed_items",
            field_value=[{"sku": "SERVER-256GB", "quantity": 1}],
            observed_at=now,
            raw_reference="pay_123",
        ),
    ]
    prior_events = [
        CanonicalEvent(
            event_id="evt_ord_001",
            transaction_id="tx_001",
            intent_id=contract.intent_id,
            event_type="order.created",
            timestamp=now - timedelta(minutes=1),
            occurred_at=now - timedelta(minutes=1),
            amount=contract.max_total,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
        ),
        CanonicalEvent(
            event_id="evt_pay_001",
            transaction_id="tx_001",
            intent_id=contract.intent_id,
            event_type="payment.captured",
            timestamp=now,
            occurred_at=now,
            amount=Money(amount=5500000, currency="INR"),
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
        ),
    ]

    # Recovery evidence: compensatory refund of 5,000 INR (500,000 paise)
    recovery_evidence = [
        Evidence(
            evidence_id="ev_refund_001",
            intent_id=contract.intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="refund_amount",
            field_value=Money(amount=500000, currency="INR"),
            observed_at=now + timedelta(seconds=2),
            raw_reference="pay_123",
        )
    ]
    recovery_events = [
        CanonicalEvent(
            event_id="evt_refund_001",
            transaction_id="tx_001",
            intent_id=contract.intent_id,
            event_type="payment.refunded",
            timestamp=now + timedelta(seconds=2),
            occurred_at=now + timedelta(seconds=2),
            amount=Money(amount=500000, currency="INR"),
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
        )
    ]

    # Revalidation
    reval_result = revalidate_recovery(
        contract=contract,
        prior_evidence=prior_evidence,
        recovery_evidence=recovery_evidence,
        prior_events=prior_events,
        recovery_events=recovery_events,
        reference_time=now + timedelta(seconds=5),
    )

    # Net amount is now 5,500,000 - 500,000 = 5,000,000 paise == contract max_total!
    assert reval_result.status == IntegrityStatus.PASS
    assert reval_result.rule_results["EconomicIntegrityRule"] is True
    assert reval_result.rule_results["SemanticIntegrityRule"] is True
    assert reval_result.rule_results["TemporalIntegrityRule"] is True
    assert len(reval_result.violations) == 0


def test_revalidate_recovery_insufficient_refund_remains_drift():
    contract = make_test_intent(max_amount_paise=5000000)
    now = datetime.now(timezone.utc)

    # Overcharge: 5,500,000 paise (500,000 paise over)
    prior_evidence = [
        Evidence(
            evidence_id="ev_orig_amount",
            intent_id=contract.intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="total_amount",
            field_value=Money(amount=5500000, currency="INR"),
            observed_at=now,
            raw_reference="pay_123",
        ),
        Evidence(
            evidence_id="ev_orig_items",
            intent_id=contract.intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="executed_items",
            field_value=[{"sku": "SERVER-256GB", "quantity": 1}],
            observed_at=now,
            raw_reference="pay_123",
        ),
    ]
    prior_events = [
        CanonicalEvent(
            event_id="evt_ord_002",
            transaction_id="tx_002",
            intent_id=contract.intent_id,
            event_type="order.created",
            timestamp=now - timedelta(minutes=1),
            occurred_at=now - timedelta(minutes=1),
            amount=contract.max_total,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
        ),
        CanonicalEvent(
            event_id="evt_pay_002",
            transaction_id="tx_002",
            intent_id=contract.intent_id,
            event_type="payment.captured",
            timestamp=now,
            occurred_at=now,
            amount=Money(amount=5500000, currency="INR"),
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
        ),
    ]

    # Insufficient partial refund of only 100,000 paise (still 400,000 paise over)
    recovery_evidence = [
        Evidence(
            evidence_id="ev_refund_insufficient",
            intent_id=contract.intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="refund_amount",
            field_value=Money(amount=100000, currency="INR"),
            observed_at=now + timedelta(seconds=2),
            raw_reference="pay_123",
        )
    ]
    recovery_events = [
        CanonicalEvent(
            event_id="evt_refund_insufficient",
            transaction_id="tx_002",
            intent_id=contract.intent_id,
            event_type="payment.refunded",
            timestamp=now + timedelta(seconds=2),
            occurred_at=now + timedelta(seconds=2),
            amount=Money(amount=100000, currency="INR"),
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
        )
    ]

    reval_result = revalidate_recovery(
        contract=contract,
        prior_evidence=prior_evidence,
        recovery_evidence=recovery_evidence,
        prior_events=prior_events,
        recovery_events=recovery_events,
        reference_time=now + timedelta(seconds=5),
    )

    # Net amount 5,400,000 still exceeds 5,000,000 -> DRIFT!
    assert reval_result.status == IntegrityStatus.DRIFT
    assert reval_result.rule_results["EconomicIntegrityRule"] is False
    assert len(reval_result.violations) > 0


# ==============================================================================
# 5. END-TO-END TRANSACTION SERVICE RECOVERY LOOP
# ==============================================================================

def test_transaction_service_end_to_end_drift_to_recovering_to_pass():
    provider = FakePaymentProvider(mock_secret=TEST_SECRET)
    service = TransactionService(default_provider=provider)

    # 1. Authorize intent for max ₹50,000 (5,000,000 paise)
    contract = make_test_intent(intent_id="intent_e2e_rec", max_amount_paise=5000000)
    create_req = CreateTransactionRequest(intent=contract)
    create_res = service.create_transaction(request=create_req, provider=provider)
    assert create_res.state == TransactionState.EXECUTING

    # 2. Simulate gateway overcharge payment: ₹55,000 (5,500,000 paise)
    overcharge_money = Money(amount=5500000, currency="INR")
    pay_id = "pay_overcharged_999"
    provider.seed_payment(
        ProviderPayment(
            payment_id=pay_id,
            order_id=create_res.order_id,
            amount=overcharge_money,
            currency="INR",
            status="captured",
            method="card",
            captured=True,
            created_at=datetime.now(timezone.utc),
            notes={"sku": "SERVER-256GB", "quantity": "1"},
        )
    )

    sig = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=pay_id,
        secret=TEST_SECRET,
    )

    # 3. Complete transaction -> detects DRIFT and generates MRDP
    comp_req = CompleteTransactionRequest(
        transaction_id=create_res.transaction_id,
        order_id=create_res.order_id,
        payment_id=pay_id,
        signature=sig,
    )
    comp_res = service.complete_transaction(request=comp_req, provider=provider)
    assert comp_res.state == TransactionState.DRIFT
    assert comp_res.integrity_status == IntegrityStatus.DRIFT
    assert comp_res.mrdp is not None
    assert comp_res.mrdp.discrepancy_amount == Money(amount=500000, currency="INR")

    # 4. Trigger Recovery Loop (T11)
    rec_req = RecoverTransactionRequest(
        transaction_id=create_res.transaction_id,
    )
    rec_res = service.recover_transaction(request=rec_req, provider=provider)

    # 5. Assert deterministic revalidation restores integrity -> PASS!
    assert rec_res.state == TransactionState.PASS
    assert rec_res.integrity_status == IntegrityStatus.PASS
    assert rec_res.rule_results["EconomicIntegrityRule"] is True
    assert rec_res.rule_results["SemanticIntegrityRule"] is True
    assert rec_res.rule_results["TemporalIntegrityRule"] is True
    assert len(rec_res.violations) == 0
    assert rec_res.mrdp is None

    # Check state machine history:
    # CREATED -> EXECUTING -> OBSERVING -> VERIFYING -> DRIFT -> RECOVERING -> REVALIDATING -> PASS
    session = service.get_session(create_res.transaction_id)
    state_names = [r.to_state.value for r in session.state_machine.history]
    assert state_names == [
        "EXECUTING",
        "OBSERVING",
        "VERIFYING",
        "DRIFT",
        "RECOVERING",
        "REVALIDATING",
        "PASS",
    ]


def test_transaction_service_non_recoverable_drift_to_abstain():
    provider = FakePaymentProvider(mock_secret=TEST_SECRET)
    service = TransactionService(default_provider=provider)

    # 1. Authorize intent for SERVER-256GB
    contract = make_test_intent(intent_id="intent_non_rec", sku="SERVER-256GB")
    create_req = CreateTransactionRequest(intent=contract)
    create_res = service.create_transaction(request=create_req, provider=provider)

    # 2. Provider payment has unauthorized SKU GPU-H100
    pay_id = "pay_bad_sku_888"
    provider.seed_payment(
        ProviderPayment(
            payment_id=pay_id,
            order_id=create_res.order_id,
            amount=contract.max_total,
            currency="INR",
            status="captured",
            method="card",
            captured=True,
            created_at=datetime.now(timezone.utc),
            notes={"sku": "GPU-H100", "quantity": "1"},
        )
    )

    sig = compute_payment_signature(
        order_id=create_res.order_id,
        payment_id=pay_id,
        secret=TEST_SECRET,
    )

    # 3. Complete transaction -> detects DRIFT (semantic)
    comp_req = CompleteTransactionRequest(
        transaction_id=create_res.transaction_id,
        order_id=create_res.order_id,
        payment_id=pay_id,
        signature=sig,
    )
    comp_res = service.complete_transaction(request=comp_req, provider=provider)
    assert comp_res.state == TransactionState.DRIFT
    assert comp_res.integrity_status == IntegrityStatus.DRIFT

    # 4. Trigger recovery -> non-recoverable semantic divergence escalates to ABSTAIN
    rec_req = RecoverTransactionRequest(
        transaction_id=create_res.transaction_id,
    )
    rec_res = service.recover_transaction(request=rec_req, provider=provider)
    assert rec_res.state == TransactionState.ABSTAIN
    assert "unauthorized sku" in rec_res.violations[0].lower()


# ==============================================================================
# 6. REST API ENDPOINT TESTS
# ==============================================================================

def test_api_recover_transaction_endpoint():
    provider = FakePaymentProvider(mock_secret=TEST_SECRET)
    test_service = TransactionService(default_provider=provider)

    app.dependency_overrides[get_payment_provider] = lambda: provider
    app.dependency_overrides[get_transaction_service] = lambda: test_service

    client = TestClient(app)

    try:
        # 1. Create transaction via API
        contract = make_test_intent(intent_id="api_tx_rec_001", max_amount_paise=5000000)
        c_res = client.post("/api/v1/transaction/create", json={"intent": contract.model_dump(mode="json")})
        assert c_res.status_code == 200
        tx_data = c_res.json()
        tx_id = tx_data["transaction_id"]
        ord_id = tx_data["order_id"]

        # 2. Seed overcharged payment in provider
        pay_id = "pay_api_overcharge_123"
        provider.seed_payment(
            ProviderPayment(
                payment_id=pay_id,
                order_id=ord_id,
                amount=Money(amount=5500000, currency="INR"),
                currency="INR",
                status="captured",
                method="card",
                captured=True,
                created_at=datetime.now(timezone.utc),
                notes={"sku": "SERVER-256GB", "quantity": "1"},
            )
        )
        sig = compute_payment_signature(order_id=ord_id, payment_id=pay_id, secret=TEST_SECRET)

        # 3. Complete transaction -> DRIFT
        comp_res = client.post(
            "/api/v1/transaction/complete",
            json={"transaction_id": tx_id, "order_id": ord_id, "payment_id": pay_id, "signature": sig},
        )
        assert comp_res.status_code == 200
        assert comp_res.json()["integrity_status"] == "DRIFT"

        # 4. Trigger recovery endpoint
        rec_res = client.post("/api/v1/transaction/recover", json={"transaction_id": tx_id})
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert rec_data["state"] == "PASS"
        assert rec_data["integrity_status"] == "PASS"
        assert rec_data["rule_results"]["EconomicIntegrityRule"] is True

    finally:
        app.dependency_overrides.clear()

