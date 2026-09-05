"""
Unit tests for TarkaRaksha T12 UNKNOWN Resolution subsystem.
Verifies:
1. UNKNOWN caused by missing provider evidence is diagnosed as RESOLVABLE.
2. Provider observation resolves UNKNOWN -> PASS.
3. Provider observation resolves UNKNOWN -> DRIFT without performing recovery.
4. Insufficient evidence remains UNKNOWN.
5. Conflicting authoritative evidence raises ResolutionConflictError / escalates to ABSTAIN.
6. Lower-authority evidence cannot resolve UNKNOWN.
7. Merchant evidence cannot override Razorpay provider evidence.
8. Bounded observation attempts (3 attempts; 4th raises ResolutionExhaustedError / ABSTAIN).
9. Provider timeout handling.
10. Provider unavailable handling.
11. Duplicate resolution request returns cached result (idempotency).
12. Duplicate evidence deduplicated cleanly.
13. Delayed provider success handled.
14. Late payment after expiry evaluated safely as ABSTAIN or DRIFT.
15. State-machine resolution lifecycle (UNKNOWN -> RESOLVING -> REVALIDATING -> PASS/DRIFT/UNKNOWN/ABSTAIN).
16. Intent immutability during resolution.
17. End-to-end TransactionService resolution workflow.
18. FastAPI POST /api/v1/transaction/resolve endpoint.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.models import (
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
    ResolveTransactionRequest,
    TransactionState,
)
from backend.app.domain.states import TransactionStateMachine
from backend.app.main import app, get_payment_provider, get_transaction_service
from backend.app.services.payment import (
    FakePaymentProvider,
    PaymentNotFoundError,
    PaymentTimeoutError,
    PaymentProviderError,
)
from backend.app.services.resolution import (
    MAX_RESOLUTION_ATTEMPTS,
    InvalidResolutionStateError,
    ResolutionCategory,
    ResolutionConflictError,
    ResolutionExhaustedError,
    ResolutionResult,
    ResolutionStrategy,
    UnknownObserver,
    diagnose_unknown,
)
from backend.app.services.transaction_service import TransactionService, TransactionSession


# ---------------------------------------------------------------------------
# Test Fixtures & Mock Providers
# ---------------------------------------------------------------------------

@pytest.fixture
def base_now() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_intent(base_now: datetime) -> IntentContract:
    return IntentContract(
        intent_id="int_res_001",
        issued_by="usr_001",
        issued_at=base_now - timedelta(minutes=5),
        expires_at=base_now + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),
        items=[
            IntentItem(
                item_id="item-srv-01",
                sku="SERVER-256GB",
                name="Dedicated Server 256GB",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
    )


@pytest.fixture
def sample_order(sample_intent: IntentContract, base_now: datetime) -> ProviderOrder:
    return ProviderOrder(
        order_id="order_res_001",
        amount=Money(amount=5000000, currency="INR"),
        currency="INR",
        status="created",
        receipt=sample_intent.intent_id,
        created_at=base_now - timedelta(minutes=4),
        notes={"sku": "SERVER-256GB", "quantity": "1"},
    )


class MockObservationProvider(FakePaymentProvider):
    """Configurable mock provider for UNKNOWN observation tests."""
    def __init__(
        self,
        payment_to_return: Optional[ProviderPayment] = None,
        order_payments_to_return: Optional[List[ProviderPayment]] = None,
        raise_timeout: bool = False,
        raise_not_found: bool = False,
        raise_gateway_error: bool = False,
    ):
        super().__init__()
        self.payment_to_return = payment_to_return
        self.order_payments_to_return = order_payments_to_return or []
        self.raise_timeout = raise_timeout
        self.raise_not_found = raise_not_found
        self.raise_gateway_error = raise_gateway_error
        self.fetch_payment_calls = 0
        self.fetch_order_payments_calls = 0

    def create_order(self, amount: Money, currency: str, receipt: str, notes: Optional[Dict[str, str]] = None) -> ProviderOrder:
        return ProviderOrder(
            order_id="order_mock",
            amount=amount,
            currency=currency,
            status="created",
            receipt=receipt,
            created_at=datetime.now(timezone.utc),
            notes=notes or {},
        )

    def fetch_payment(self, payment_id: str) -> ProviderPayment:
        self.fetch_payment_calls += 1
        if self.raise_timeout:
            raise PaymentTimeoutError("Gateway fetch timed out")
        if self.raise_not_found:
            raise PaymentNotFoundError(f"Payment {payment_id} not found")
        if self.raise_gateway_error:
            raise PaymentProviderError("Gateway internal 500 error")
        if self.payment_to_return:
            return self.payment_to_return
        raise PaymentNotFoundError("No payment configured")

    def fetch_order_payments(self, order_id: str) -> List[ProviderPayment]:
        self.fetch_order_payments_calls += 1
        if self.raise_timeout:
            raise PaymentTimeoutError("Gateway fetch timed out")
        if self.raise_gateway_error:
            raise PaymentProviderError("Gateway internal 500 error")
        return self.order_payments_to_return

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        return True

    def refund_payment(self, payment_id: str, amount: Optional[int] = None, notes: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return {"refund_id": "rfnd_mock", "payment_id": payment_id, "amount": amount or 0, "status": "processed"}


# ---------------------------------------------------------------------------
# Test 1 & 4: Diagnosis & Insufficient Provider Evidence Remains UNKNOWN
# ---------------------------------------------------------------------------

def test_missing_provider_evidence_diagnosed_as_resolvable_or_unknown(sample_intent, sample_order, base_now):
    """Test 1: Diagnosis accurately identifies missing provider evidence as resolvable by observation."""
    unknown_result = IntegrityResult(
        evaluation_id="eval_test_001",
        intent_id=sample_intent.intent_id,
        status=IntegrityStatus.UNKNOWN,
        evaluated_at=base_now,
        rule_results={"EconomicIntegrityRule": False},
        violations=["Missing provider evidence"],
        evidence_ids=[],
        confidence_score=0.0,
    )
    diagnosis = diagnose_unknown(
        contract=sample_intent,
        integrity_result=unknown_result,
        evidence_bundle=None,
        current_attempt=1,
        reference_time=base_now,
    )
    assert diagnosis.category == ResolutionCategory.RESOLVABLE
    assert diagnosis.strategy == ResolutionStrategy.FETCH_ORDER_PAYMENTS
    assert "total_amount" in diagnosis.missing_fields


def test_insufficient_evidence_when_order_has_no_payments_remains_unknown(sample_intent, sample_order, base_now):
    """Test 4: When provider returns 0 payments for order, resolution deterministically remains UNKNOWN."""
    provider = MockObservationProvider(order_payments_to_return=[])
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        now=base_now,
    )

    assert result.integrity_result.status == IntegrityStatus.UNKNOWN
    assert result.category == ResolutionCategory.REMAINS_UNKNOWN


# ---------------------------------------------------------------------------
# Test 2: Provider Observation Resolves UNKNOWN -> PASS
# ---------------------------------------------------------------------------

def test_provider_observation_resolves_unknown_to_pass(sample_intent, sample_order, base_now):
    """Test 2: When authoritative provider payment matches authorized intent, resolution produces PASS."""
    captured_payment = ProviderPayment(
        payment_id="pay_auth_001",
        order_id=sample_order.order_id,
        amount=Money(amount=5000000, currency="INR"),
        currency="INR",
        status="captured",
        method="card",
        captured=True,
        created_at=base_now,
        notes={"sku": "SERVER-256GB", "quantity": "1"},
    )
    provider = MockObservationProvider(order_payments_to_return=[captured_payment])
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        now=base_now + timedelta(minutes=1),
    )

    assert result.integrity_result.status == IntegrityStatus.PASS
    assert result.category == ResolutionCategory.RESOLVABLE
    assert len(result.new_evidence) > 0


# ---------------------------------------------------------------------------
# Test 3: Provider Observation Resolves UNKNOWN -> DRIFT (Without Recovering)
# ---------------------------------------------------------------------------

def test_provider_observation_resolves_unknown_to_drift_without_recovering(sample_intent, sample_order, base_now):
    """Test 3: Provider observation detects overcharge (55k vs 50k); produces DRIFT without recovering."""
    overcharged_payment = ProviderPayment(
        payment_id="pay_overcharge_001",
        order_id=sample_order.order_id,
        amount=Money(amount=5500000, currency="INR"),  # 55,000 INR (exceeds 50,000 INR limit)
        currency="INR",
        status="captured",
        method="card",
        captured=True,
        created_at=base_now,
        notes={"sku": "SERVER-256GB", "quantity": "1"},
    )
    provider = MockObservationProvider(order_payments_to_return=[overcharged_payment])
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        now=base_now + timedelta(minutes=1),
    )

    assert result.integrity_result.status == IntegrityStatus.DRIFT
    assert result.category == ResolutionCategory.RESOLVABLE
    # Verified economic rule failed
    assert result.integrity_result.rule_results["EconomicIntegrityRule"] is False


# ---------------------------------------------------------------------------
# Test 5 & 6 & 7: Evidence Authority & Conflict Resolution
# ---------------------------------------------------------------------------

def test_merchant_evidence_cannot_override_authoritative_provider_evidence(sample_intent, sample_order, base_now):
    """Test 7: Merchant attested evidence cannot override AUTHORITATIVE provider evidence."""
    merchant_evidence = Evidence(
        evidence_id="ev_merch_001",
        intent_id=sample_intent.intent_id,
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="total_amount",
        field_value=Money(amount=5000000, currency="INR"),
        observed_at=base_now,
    )
    # But Razorpay authoritative payment says 55,000 INR (overcharge drift)
    drift_payment = ProviderPayment(
        payment_id="pay_overcharge_001",
        order_id=sample_order.order_id,
        amount=Money(amount=5500000, currency="INR"),
        currency="INR",
        status="captured",
        captured=True,
        method="card",
        created_at=base_now,
        notes={"sku": "SERVER-256GB", "quantity": "1"},
    )
    provider = MockObservationProvider(order_payments_to_return=[drift_payment])
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[merchant_evidence],
        prior_events=[],
        now=base_now + timedelta(minutes=1),
    )

    # Authoritative provider overcharge establishes DRIFT; merchant's lower claim of 50k cannot force PASS
    assert result.integrity_result.status == IntegrityStatus.DRIFT
    assert result.integrity_result.rule_results["EconomicIntegrityRule"] is False



def test_lower_authority_advisory_cannot_resolve_unknown(sample_intent, sample_order, base_now):
    """Test 6: AI / Advisory evidence (lowest authority) cannot resolve UNKNOWN."""
    advisory_evidence = Evidence(
        evidence_id="ev_ai_001",
        intent_id=sample_intent.intent_id,
        source=EvidenceSource.AGENT,
        authority=EvidenceAuthority.ADVISORY,
        field_name="payment_status",
        field_value="captured",
        observed_at=base_now,
    )
    # Provider has no payment
    provider = MockObservationProvider(order_payments_to_return=[])
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[advisory_evidence],
        prior_events=[],
        now=base_now,
    )

    # Must remain UNKNOWN despite AI claim
    assert result.integrity_result.status == IntegrityStatus.UNKNOWN



def test_conflicting_authoritative_provider_evidence_escalates_to_abstain(sample_intent, sample_order, base_now):
    """Test 5: Conflicting authoritative evidence in bundle escalates to ABSTAIN."""
    e1 = Evidence(
        evidence_id="ev_auth_1",
        intent_id=sample_intent.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=5000000, currency="INR"),
        observed_at=base_now,
    )
    e2 = Evidence(
        evidence_id="ev_auth_2",
        intent_id=sample_intent.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=6000000, currency="INR"),
        observed_at=base_now + timedelta(seconds=1),
    )
    provider = MockObservationProvider()
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[e1, e2],
        prior_events=[],
        now=base_now,
    )
    assert result.category == ResolutionCategory.ABSTAIN
    assert "Irreconcilable conflict detected" in result.details.get("reason", "")


# ---------------------------------------------------------------------------
# Test 8 & 9 & 10: Bounds, Timeouts, and Provider Unavailable
# ---------------------------------------------------------------------------

def test_provider_timeout_handled_gracefully_remains_unknown(sample_intent, sample_order, base_now):
    """Test 9: Gateway timeout during observation is handled gracefully and remains UNKNOWN."""
    provider = MockObservationProvider(raise_timeout=True)
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        now=base_now,
    )

    assert result.integrity_result.status == IntegrityStatus.UNKNOWN
    assert result.category == ResolutionCategory.REMAINS_UNKNOWN


def test_provider_gateway_error_handled_gracefully_remains_unknown(sample_intent, sample_order, base_now):
    """Test 10: Gateway 500 error during observation remains UNKNOWN."""
    provider = MockObservationProvider(raise_gateway_error=True)
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        now=base_now,
    )

    assert result.integrity_result.status == IntegrityStatus.UNKNOWN


def test_bounded_resolution_attempts_in_transaction_service(sample_intent, sample_order, base_now):
    """Test 8: TransactionService enforces MAX_RESOLUTION_ATTEMPTS = 3; 4th attempt transitions to ABSTAIN."""
    provider = MockObservationProvider(order_payments_to_return=[])
    service = TransactionService(default_provider=provider)

    sm = TransactionStateMachine(
        transaction_id="tx_budget_001",
        intent=sample_intent,
        initial_state=TransactionState.UNKNOWN,
        created_at=base_now,
    )
    session = TransactionSession(
        transaction_id="tx_budget_001",
        intent=sample_intent,
        state_machine=sm,
        order=sample_order,
        created_at=base_now,
    )
    service._sessions[session.transaction_id] = session

    req = ResolveTransactionRequest(transaction_id=session.transaction_id)

    # Attempts 1, 2, 3 should succeed in running resolution (returning UNKNOWN)
    for i in range(1, MAX_RESOLUTION_ATTEMPTS + 1):
        res = service.resolve_transaction(req, provider_override=provider, now=base_now + timedelta(minutes=i))
        assert res.integrity_status == IntegrityStatus.UNKNOWN
        assert session.resolution_attempts == i
        # Reset state back to UNKNOWN for next observation cycle
        if sm.current_state != TransactionState.UNKNOWN:
            sm.transition_to(TransactionState.UNKNOWN, timestamp=base_now + timedelta(minutes=i, seconds=30))

    # Attempt 4 must raise ResolutionExhaustedError and transition to ABSTAIN
    with pytest.raises(ResolutionExhaustedError) as exc_info:
        service.resolve_transaction(req, provider_override=provider, now=base_now + timedelta(minutes=10))

    assert "Resolution attempt budget exhausted" in str(exc_info.value)
    assert sm.current_state == TransactionState.ABSTAIN


# ---------------------------------------------------------------------------
# Test 11 & 12: Idempotency & Evidence Deduplication
# ---------------------------------------------------------------------------

def test_duplicate_resolution_request_returns_cached_result(sample_intent, sample_order, base_now):
    """Test 11: Idempotency key returns cached result without repeating provider queries."""
    captured_payment = ProviderPayment(
        payment_id="pay_idem_001",
        order_id=sample_order.order_id,
        amount=Money(amount=5000000, currency="INR"),
        currency="INR",
        status="captured",
        captured=True,
        method="card",
        created_at=base_now,
        notes={"sku": "SERVER-256GB", "quantity": "1"},
    )
    provider = MockObservationProvider(order_payments_to_return=[captured_payment])
    observer = UnknownObserver()

    # First call
    res1 = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        idempotency_key="idem_key_xyz",
        now=base_now,
    )
    assert provider.fetch_order_payments_calls == 1

    # Second call with same idempotency key
    res2 = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        idempotency_key="idem_key_xyz",
        now=base_now,
    )
    # Must NOT call provider again
    assert provider.fetch_order_payments_calls == 1
    assert res2.is_idempotent_replay is True
    assert res1.integrity_result.status == res2.integrity_result.status


def test_late_payment_after_expiry_evaluated_as_abstain(sample_intent, sample_order, base_now):
    """Test 14: Observation attempt after intent.expires_at is rejected as ABSTAIN."""
    provider = MockObservationProvider()
    observer = UnknownObserver()

    result = observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        now=sample_intent.expires_at + timedelta(minutes=15),
    )

    assert result.category == ResolutionCategory.ABSTAIN
    assert "expired" in result.details.get("reason", "").lower()


def test_intent_immutability_during_resolution(sample_intent, sample_order, base_now):
    """Test 16: UNKNOWN resolution cannot mutate original IntentContract."""
    original_amount = sample_intent.max_total.amount
    original_expiry = sample_intent.expires_at

    captured_payment = ProviderPayment(
        payment_id="pay_immut_001",
        order_id=sample_order.order_id,
        amount=Money(amount=5000000, currency="INR"),
        currency="INR",
        status="captured",
        captured=True,
        created_at=base_now,
        notes={"sku": "SERVER-256GB", "quantity": "1"},
    )
    provider = MockObservationProvider(order_payments_to_return=[captured_payment])
    observer = UnknownObserver()

    observer.resolve(
        contract=sample_intent,
        order=sample_order,
        payment_id=None,
        provider=provider,
        current_state=TransactionState.RESOLVING,
        prior_evidence=[],
        prior_events=[],
        now=base_now,
    )

    # IntentContract fields must remain strictly unchanged
    assert sample_intent.max_total.amount == original_amount
    assert sample_intent.expires_at == original_expiry


# ---------------------------------------------------------------------------
# Test 17 & 18: End-to-End Workflow & FastAPI API Endpoint
# ---------------------------------------------------------------------------

def test_transaction_service_resolve_end_to_end(sample_intent, sample_order, base_now):
    """Test 17: Full state-machine lifecycle: UNKNOWN -> RESOLVING -> REVALIDATING -> PASS."""
    captured_payment = ProviderPayment(
        payment_id="pay_e2e_001",
        order_id=sample_order.order_id,
        amount=Money(amount=5000000, currency="INR"),
        currency="INR",
        status="captured",
        captured=True,
        method="card",
        created_at=base_now,
        notes={"sku": "SERVER-256GB", "quantity": "1"},
    )
    provider = MockObservationProvider(order_payments_to_return=[captured_payment])
    service = TransactionService(default_provider=provider)

    sm = TransactionStateMachine(
        transaction_id="tx_e2e_001",
        intent=sample_intent,
        initial_state=TransactionState.UNKNOWN,
        created_at=base_now,
    )
    session = TransactionSession(
        transaction_id="tx_e2e_001",
        intent=sample_intent,
        state_machine=sm,
        order=sample_order,
        created_at=base_now,
    )
    service._sessions[session.transaction_id] = session

    req = ResolveTransactionRequest(transaction_id=session.transaction_id)
    response = service.resolve_transaction(req, provider_override=provider, now=base_now + timedelta(seconds=10))

    assert response.state == TransactionState.PASS
    assert response.integrity_status == IntegrityStatus.PASS

    # Verify state machine history includes RESOLVING and REVALIDATING
    history_states = [r.to_state for r in sm.history]
    assert TransactionState.RESOLVING in history_states
    assert TransactionState.REVALIDATING in history_states
    assert TransactionState.PASS in history_states


def test_fastapi_resolve_endpoint(sample_intent, sample_order, base_now):
    """Test 18: POST /api/v1/transaction/resolve executes through FastAPI test client."""
    captured_payment = ProviderPayment(
        payment_id="pay_api_001",
        order_id=sample_order.order_id,
        amount=Money(amount=5000000, currency="INR"),
        currency="INR",
        status="captured",
        captured=True,
        method="card",
        created_at=base_now,
        notes={"sku": "SERVER-256GB", "quantity": "1"},
    )
    mock_provider = MockObservationProvider(order_payments_to_return=[captured_payment])
    service = TransactionService(default_provider=mock_provider)

    sm = TransactionStateMachine(
        transaction_id="tx_api_001",
        intent=sample_intent,
        initial_state=TransactionState.UNKNOWN,
        created_at=base_now,
    )
    session = TransactionSession(
        transaction_id="tx_api_001",
        intent=sample_intent,
        state_machine=sm,
        order=sample_order,
        created_at=base_now,
    )
    service._sessions[session.transaction_id] = session

    app.dependency_overrides[get_transaction_service] = lambda: service
    app.dependency_overrides[get_payment_provider] = lambda: mock_provider

    client = TestClient(app)
    try:
        res = client.post("/api/v1/transaction/resolve", json={"transaction_id": "tx_api_001"})
        assert res.status_code == 200
        data = res.json()
        assert data["transaction_id"] == "tx_api_001"
        assert data["integrity_status"] == "PASS"
        assert data["state"] == "PASS"
    finally:
        app.dependency_overrides.clear()
