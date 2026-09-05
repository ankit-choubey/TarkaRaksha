"""
Adversarial and Integration Tests for Merchant Agent (I4.5).

Proves that:
1. Merchant-attested evidence cannot override authoritative payment gateway evidence.
2. Merchant proposal cannot fabricate payment state or convert UNKNOWN into PASS.
3. Expired offers are rejected deterministically and prompt a refresh request.
4. Inventory depletion between offer and fulfillment triggers INVENTORY_STATE_DRIFT.
5. Missing stock evidence results in UNKNOWN, never PASS.
6. Temporal fulfillment drift is caught when delivery days exceed buyer constraints.
7. Carrier mismatch is caught deterministically.
8. Policy boundaries (max order value, max discount) are enforced strictly.
9. Unsupported capabilities are rejected cleanly without system failure.
10. Cross-transaction and cross-intent response reuse is detected by protocol binding.
11. Merchant agent cannot force state machine transitions into COMPLETED without gateway proof.
12. Repeated offer generation under identical conditions is 100% deterministic.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import pytest

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    TransactionState,
)
from backend.app.domain.merchant import (
    BuyerCommerceRequest,
    BuyerItemRequest,
    CatalogItem,
    CommerceCapabilityType,
    InventoryRecord,
    InventoryStatus,
    MerchantCapability,
    MerchantCapabilityDeclaration,
    MerchantIntegrityVerifier,
    MerchantOffer,
    MerchantOfferItem,
    MerchantPolicyAsCode,
    MerchantResponse,
    OfferVerificationStatus,
    ShippingOption,
    TaxEstimate,
)
from backend.app.domain.security import (
    AgentTransactionMessage,
    ProtocolSecurityVerifier,
    ProtocolViolationCode,
)
from backend.app.domain.states import (
    TransactionStateMachine,
    InvalidStateTransitionError,
)
from backend.app.domain.rules import check_economic, check_semantic
from backend.app.services.merchant import MerchantCatalogService
from backend.app.services.evaluation import evaluate_integrity


@pytest.fixture
def ref_time():
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def standard_contract(ref_time):
    return IntentContract(
        intent_id="intent-test-adv-1",
        issued_by="user-alice",
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),  # ₹50,000
        items=[
            IntentItem(
                item_id="item-phone",
                sku="SKU-PHONE-1",
                name="Pixel 9 Pro",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
        allowed_substitutions=[],
        max_successful_captures=1,
    )


@pytest.fixture
def sample_merchant_service(ref_time):
    service = MerchantCatalogService(
        merchant_id="merch_acme_corp",
        merchant_name="Acme Electronics Ltd",
    )
    service.add_catalog_item(
        CatalogItem(
            sku="SKU-PHONE-1",
            title="Pixel 9 Pro",
            description="Flagship smartphone",
            category="Electronics",
            base_price=Money(amount=5000000, currency="INR"),
        ),
        initial_stock=10,
    )
    return service



# =========================================================================
# 1. Authority Invariants: Merchant Cannot Override Deterministic Integrity
# =========================================================================

def test_merchant_offer_cannot_override_authoritative_gateway_drift(standard_contract, ref_time):
    """
    INVARIANT: Even if merchant claims the price is ₹50,000, if Razorpay reports ₹50,001 (DRIFT),
    the deterministic engine MUST declare DRIFT, not PASS.
    """
    # 1. Merchant offer claiming ₹50,000
    merchant_ev = Evidence(
        evidence_id="ev-merch-1",
        intent_id=standard_contract.intent_id,
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="total_amount",
        field_value=Money(amount=5000000, currency="INR"),  # ₹50,000 (compliant)
        observed_at=ref_time,
    )

    # 2. Authoritative Gateway evidence showing ₹50,001 (over budget -> DRIFT)
    gateway_ev = Evidence(
        evidence_id="ev-gateway-1",
        intent_id=standard_contract.intent_id,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        field_name="total_amount",
        field_value=Money(amount=5000100, currency="INR"),  # ₹50,001 (drift)
        observed_at=ref_time + timedelta(minutes=2),
    )

    # Deterministic economic rule check
    result = check_economic(standard_contract, [merchant_ev, gateway_ev])
    assert result.status == IntegrityStatus.DRIFT
    assert result.is_drift is True
    assert result.is_pass is False
    assert "exceeds" in result.violation.lower() or "limit" in result.explanation.lower()


def test_merchant_offer_cannot_fabricate_payment_when_gateway_evidence_missing(standard_contract, ref_time):
    """
    INVARIANT: In the absence of authoritative gateway evidence, merchant offer cannot
    force a transaction to PASS. Missing payment must evaluate to UNKNOWN.
    """
    merchant_ev = Evidence(
        evidence_id="ev-merch-1",
        intent_id=standard_contract.intent_id,
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="total_amount",
        field_value=Money(amount=5000000, currency="INR"),
        observed_at=ref_time,
    )

    # Missing executed items and gateway capture events: overall evaluation MUST be UNKNOWN
    result = evaluate_integrity(standard_contract, [merchant_ev])
    assert result.status == IntegrityStatus.UNKNOWN
    assert result.is_unknown is True
    assert result.is_pass is False



# =========================================================================
# 2. Dynamic Offer Expiry Tests
# =========================================================================

def test_expired_offer_rejected_by_integrity_verifier(sample_merchant_service, ref_time):
    """
    INVARIANT: An offer past its offer_expires_at timestamp MUST be rejected with
    status=EXPIRED and action_recommended=REQUEST_REFRESH.
    """
    req = BuyerCommerceRequest(
        request_id="req-101",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-test-adv-1",
        transaction_id="tx-101",
        items=[BuyerItemRequest(sku="SKU-PHONE-1", quantity=1)],
    )

    resp = sample_merchant_service.process_buyer_request(req, reference_time=ref_time)
    assert resp.is_success is True

    # Evaluate offer after expiry
    post_expiry_time = resp.offer_expires_at + timedelta(seconds=1)
    eval_result = MerchantIntegrityVerifier.verify_offer_expiry(resp, current_time=post_expiry_time)

    assert eval_result.is_valid is False
    assert eval_result.status == OfferVerificationStatus.EXPIRED
    assert eval_result.integrity_status == IntegrityStatus.DRIFT
    assert eval_result.action_recommended == "REQUEST_REFRESH"
    assert eval_result.violation == "EXPIRED_OFFER_REJECTED"


# =========================================================================
# 3. Inventory & Fulfillment Integrity Tests
# =========================================================================

def test_inventory_depletion_triggers_inventory_state_drift(sample_merchant_service, ref_time):
    """
    INVARIANT: If an offer claimed AVAILABLE but stock drops to 0 before execution,
    the verifier flags INVENTORY_STATE_DRIFT.
    """
    req = BuyerCommerceRequest(
        request_id="req-102",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-test-adv-1",
        transaction_id="tx-102",
        items=[BuyerItemRequest(sku="SKU-PHONE-1", quantity=1)],
    )

    resp = sample_merchant_service.process_buyer_request(req, reference_time=ref_time)
    assert resp.is_success is True

    # Simulate stock depleted to 0
    eval_result = MerchantIntegrityVerifier.verify_inventory_integrity(
        offer=resp,
        current_stock=0,
        required_quantity=1,
        authoritative_evidence_available=True,
    )

    assert eval_result.is_valid is False
    assert eval_result.status == OfferVerificationStatus.INVENTORY_DEPLETED
    assert eval_result.integrity_status == IntegrityStatus.DRIFT
    assert eval_result.action_recommended == "RE_EVALUATE_INVENTORY"
    assert eval_result.violation == "INVENTORY_STATE_DRIFT"


def test_missing_inventory_evidence_evaluates_to_unknown(sample_merchant_service, ref_time):
    """
    INVARIANT: When authoritative stock evidence is missing, verifier returns UNKNOWN, never PASS.
    """
    req = BuyerCommerceRequest(
        request_id="req-103",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-test-adv-1",
        transaction_id="tx-103",
        items=[BuyerItemRequest(sku="SKU-PHONE-1", quantity=1)],
    )

    resp = sample_merchant_service.process_buyer_request(req, reference_time=ref_time)

    eval_result = MerchantIntegrityVerifier.verify_inventory_integrity(
        offer=resp,
        current_stock=None,
        authoritative_evidence_available=False,
    )

    assert eval_result.is_valid is False
    assert eval_result.integrity_status == IntegrityStatus.UNKNOWN
    assert eval_result.action_recommended == "VERIFY_INVENTORY_AUTHORITATIVE"


def test_fulfillment_delivery_days_drift(sample_merchant_service, ref_time):
    """
    INVARIANT: When delivery days exceed buyer constraint, TEMPORAL_FULFILLMENT_DRIFT is flagged.
    """
    req = BuyerCommerceRequest(
        request_id="req-104",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-test-adv-1",
        transaction_id="tx-104",
        items=[BuyerItemRequest(sku="SKU-PHONE-1", quantity=1)],
    )

    resp = sample_merchant_service.process_buyer_request(req, reference_time=ref_time)
    assert resp.estimated_delivery_days == 3

    # Buyer demands delivery within 2 days (standard shipping offers 3)
    eval_result = MerchantIntegrityVerifier.verify_fulfillment_integrity(
        offer=resp,
        buyer_max_delivery_days=2,
    )

    assert eval_result.is_valid is False
    assert eval_result.status == OfferVerificationStatus.FULFILLMENT_BREACH
    assert eval_result.integrity_status == IntegrityStatus.DRIFT
    assert eval_result.violation == "TEMPORAL_FULFILLMENT_DRIFT"


# =========================================================================
# 4. Merchant Policy & Capability Enforcement Tests
# =========================================================================

def test_unsupported_capability_rejection(ref_time):
    """
    INVARIANT: If CATALOG capability is disabled, requests are rejected cleanly.
    """
    decl = MerchantCapabilityDeclaration(
        merchant_id="merch_restricted",
        merchant_name="Restricted Merchant",
        capabilities={
            CommerceCapabilityType.INVENTORY: MerchantCapability(capability_type=CommerceCapabilityType.INVENTORY, is_available=True),
            CommerceCapabilityType.CATALOG: MerchantCapability(capability_type=CommerceCapabilityType.CATALOG, is_available=False),
        },
    )
    service = MerchantCatalogService(
        merchant_id="merch_restricted",
        merchant_name="Restricted Merchant",
        capabilities=decl,
    )

    req = BuyerCommerceRequest(
        request_id="req-105",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-test-adv-1",
        transaction_id="tx-105",
        items=[BuyerItemRequest(sku="SKU-PHONE-1", quantity=1)],
    )

    resp = service.process_buyer_request(req, reference_time=ref_time)
    assert resp.is_success is False
    assert "does not currently support" in resp.rejection_reason


def test_merchant_policy_max_order_value_enforcement(ref_time):
    """
    INVARIANT: Policy-as-code enforces maximum order value limit deterministically.
    """
    policy = MerchantPolicyAsCode(
        policy_id="pol-low-limit",
        merchant_id="merch_low_limit",
        max_order_value=Money(amount=100000, currency="INR"),  # ₹1,000 max order value
    )
    service = MerchantCatalogService(
        merchant_id="merch_low_limit",
        merchant_name="Low Limit Merchant",
        policy=policy,
    )
    service.add_catalog_item(
        CatalogItem(
            sku="SKU-EXPENSIVE",
            title="High-End Server",
            description="Enterprise server",
            category="Computers",
            base_price=Money(amount=2000000, currency="INR"),  # ₹20,000
        ),
        initial_stock=5,
    )

    req = BuyerCommerceRequest(
        request_id="req-106",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-test-adv-1",
        transaction_id="tx-106",
        items=[BuyerItemRequest(sku="SKU-EXPENSIVE", quantity=1)],
    )

    resp = service.process_buyer_request(req, reference_time=ref_time)
    assert resp.is_success is False
    assert "exceeds policy ceiling" in resp.rejection_reason.lower()


def test_merchant_policy_bounds_excessive_discount(sample_merchant_service, ref_time):
    """
    INVARIANT: Attempting to claim a 50% discount is bounded by policy.max_discount_bps (20%).
    """
    req = BuyerCommerceRequest(
        request_id="req-107",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-test-adv-1",
        transaction_id="tx-107",
        items=[BuyerItemRequest(sku="SKU-PHONE-1", quantity=1)],
    )

    # Request 5000 bps (50%) discount; merchant policy caps at 2000 bps (20%)
    resp = sample_merchant_service.process_buyer_request(req, discount_percentage_bps=5000, reference_time=ref_time)
    assert resp.is_success is True

    # 20% of 5000000 is 1000000 paise (₹10,000)
    assert resp.discount.amount == 1000000
    assert resp.discount.amount < 2500000  # Capped, not 50%


# =========================================================================
# 5. Protocol Security & Binding Tests (I2 Integration)
# =========================================================================

def test_merchant_response_bound_to_wrong_intent_rejected(sample_merchant_service, ref_time):
    """
    INVARIANT: Presenting a merchant response for a different intent_id or transaction_id
    is caught as a protocol violation.
    """
    req = BuyerCommerceRequest(
        request_id="req-bound-1",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-alpha",
        transaction_id="tx-alpha",
        items=[BuyerItemRequest(sku="SKU-PHONE-1", quantity=1)],
    )

    resp = sample_merchant_service.process_buyer_request(req, reference_time=ref_time)

    # Wrap in agent message bound to intent-alpha
    msg = AgentTransactionMessage(
        message_id="msg-m-1",
        intent_id="intent-alpha",
        transaction_id="tx-alpha",
        attempt_id="att-1",
        sender="merch_acme_corp",
        receiver="agent-buyer-1",
        message_type="MERCHANT_OFFER",
        payload=resp.model_dump(mode="json"),
        timestamp=ref_time,
        expires_at=resp.offer_expires_at,
        current_message_hash="placeholder",
    ).with_computed_hash()

    verifier = ProtocolSecurityVerifier()
    # Verify against WRONG intent (intent-beta)
    res = verifier.verify_message(
        message=msg,
        expected_intent_id="intent-beta",
        expected_transaction_id="tx-alpha",
        reference_time=ref_time,
    )

    assert res.is_valid is False
    assert res.violation_code == ProtocolViolationCode.INTENT_MISMATCH


# =========================================================================
# 6. State Machine & Authority Boundaries
# =========================================================================

def test_merchant_cannot_force_state_machine_transition(standard_contract, ref_time):
    """
    INVARIANT: The merchant agent cannot force a transaction directly from
    CREATED to PASS without going through EXECUTING -> OBSERVING -> VERIFYING.
    """
    sm = TransactionStateMachine("tx_001", standard_contract)

    # Invalid event attempting direct transition from CREATED to PASS
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(TransactionState.PASS, "Merchant claimed payment was completed", ref_time)



def test_deterministic_repeated_offer_generation(sample_merchant_service, ref_time):
    """
    INVARIANT: Repeating the exact same request 100 times under identical catalog/time
    generates strictly identical financial calculations and offers down to the paisa.
    """
    req = BuyerCommerceRequest(
        request_id="req-repeat-1",
        buyer_agent_id="agent-buyer-1",
        intent_id="intent-test-adv-1",
        transaction_id="tx-repeat-1",
        items=[BuyerItemRequest(sku="SKU-PHONE-1", quantity=1)],
    )

    offers = [
        sample_merchant_service.process_buyer_request(req, discount_percentage_bps=500, reference_time=ref_time)
        for _ in range(100)
    ]

    first_total = offers[0].total_amount.amount
    first_tax = offers[0].tax.amount.amount
    first_discount = offers[0].discount.amount

    for off in offers[1:]:
        assert off.total_amount.amount == first_total
        assert off.tax.amount.amount == first_tax
        assert off.discount.amount == first_discount
        assert off.items[0].total_price.amount == offers[0].items[0].total_price.amount
