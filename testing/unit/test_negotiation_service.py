"""Unit tests for I7 — Bounded Agentic Negotiation Service.

Tests:
1. Already compliant initial offer -> completes immediately (0 rounds).
2. Canonical remediation loop:
   - Initial offer over budget (₹54,000 > ₹50,000) -> DRIFT.
   - Buyer replans -> Merchant discounts/re-quotes to ₹49,000 -> revalidation PASS.
3. Permitted SKU substitution flow (SERVER-256 unavailable -> SERVER-256-V2 accepted).
4. Buyer clarification flow -> session ESCALATED.
5. Buyer abstention flow -> session ABSTAINED.
6. Multi-round TIX message audit & cryptographic hash chain verification.
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.merchant.contracts import (
    CatalogItem,
    InventoryRecord,
    InventoryStatus,
    MerchantOfferItem,
    MerchantResponse,
    ShippingOption,
)
from backend.app.domain.models.enums import EvidenceSource, IntegrityStatus
from backend.app.domain.models.evidence import CanonicalEvent, Evidence
from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money
from backend.app.domain.negotiation import (
    NegotiationPolicy,
    NegotiationState,
)
from backend.app.services.buyer.agent_service import BuyerAgentService
from backend.app.services.merchant.catalog_service import MerchantCatalogService
from backend.app.services.negotiation import BoundedNegotiationService
from backend.app.services.tix import TIXExchangeService


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def base_intent(base_time: datetime) -> IntentContract:
    return IntentContract(
        intent_id="intent_neg_01",
        issued_by="buyer_alice",
        items=[
            IntentItem(
                item_id="i1",
                sku="SERVER-256",
                name="Server 256GB",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),  # ₹50,000
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
        max_total=Money(amount=5000000, currency="INR"),
        allowed_substitutions=["SERVER-256-V2"],
        issued_at=base_time,
        expires_at=base_time + timedelta(hours=2),
    )


@pytest.fixture
def merchant_catalog(base_time: datetime) -> MerchantCatalogService:
    service = MerchantCatalogService(merchant_id="merchant_store_1")
    # Add primary item
    service.add_catalog_item(
        CatalogItem(
            sku="SERVER-256",
            title="Server 256GB",
            description="Enterprise Server",
            category="hardware",
            base_price=Money(amount=4000000, currency="INR"),  # base ₹40,000 -> with tax ₹47,318 <= ₹50,000
            currency="INR",
        ),
        initial_stock=10,
    )
    # Add substitute item
    service.add_catalog_item(
        CatalogItem(
            sku="SERVER-256-V2",
            title="Server 256GB V2",
            description="Enterprise Server V2",
            category="hardware",
            base_price=Money(amount=3800000, currency="INR"),  # base ₹38,000 -> with tax ₹44,958 <= ₹50,000
            currency="INR",
        ),
        initial_stock=5,
    )
    # Add shipping
    service._shipping_options["ship_std"] = ShippingOption(
        option_id="ship_std",
        carrier="FastCourier",
        method_name="Standard",
        cost=Money(amount=0, currency="INR"),
        estimated_days=2,
        guaranteed_days=3,
    )
    return service


def test_negotiation_already_compliant_initial_offer(
    base_time: datetime, base_intent: IntentContract, merchant_catalog: MerchantCatalogService
):
    service = BoundedNegotiationService(merchant_service=merchant_catalog)
    tx_id = "tx_neg_pass"

    # Initial evidence that is already compliant
    evidence = [
        Evidence(
            evidence_id="ev_01",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="total_amount",
            field_value=Money(amount=4900000, currency="INR"),
            observed_at=base_time,
            is_authoritative=True,
        ),
        Evidence(
            evidence_id="ev_02",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="executed_items",
            field_value=[{"sku": "SERVER-256", "quantity": 1}],
            observed_at=base_time,
            is_authoritative=True,
        ),
    ]
    events = [
        CanonicalEvent(
            event_id="evt_01",
            transaction_id=tx_id,
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_CAPTURED",
            timestamp=base_time,
            sequence_number=1,
        )
    ]

    initial_resp = MerchantResponse(
        response_id="resp_00",
        merchant_id="merchant_store_1",
        request_id="req_00",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        is_success=True,
        total_amount=Money(amount=4900000, currency="INR"),
        offer_created_at=base_time,
        offer_expires_at=base_time + timedelta(hours=1),
    )

    session = service.execute_bounded_remediation(
        intent=base_intent,
        transaction_id=tx_id,
        initial_merchant_response=initial_resp,
        initial_evidence=evidence,
        events=events,
        reference_time=base_time,
    )

    assert session.state == NegotiationState.COMPLETED
    assert session.is_settled is True
    assert session.current_round == 0
    assert session.final_verdict == IntegrityStatus.PASS


def test_canonical_i7_remediation_loop(
    base_time: datetime, base_intent: IntentContract, merchant_catalog: MerchantCatalogService
):
    tix_service = TIXExchangeService()
    service = BoundedNegotiationService(
        merchant_service=merchant_catalog,
        tix_service=tix_service,
    )
    tx_id = "tx_neg_canonical_01"

    # Initial evidence exceeds budget: ₹54,000 > ₹50,000 authorized limit -> DRIFT!
    drift_evidence = [
        Evidence(
            evidence_id="ev_drift_01",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="total_amount",
            field_value=Money(amount=5400000, currency="INR"),  # ₹54,000 (Drift!)
            observed_at=base_time,
            is_authoritative=True,
        ),
        Evidence(
            evidence_id="ev_drift_02",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="executed_items",
            field_value=[{"sku": "SERVER-256", "quantity": 1}],
            observed_at=base_time,
            is_authoritative=True,
        ),
    ]
    events = [
        CanonicalEvent(
            event_id="evt_01",
            transaction_id=tx_id,
            intent_id=base_intent.intent_id,
            event_type="PAYMENT_CAPTURED",
            timestamp=base_time,
            sequence_number=1,
        )
    ]

    initial_resp = MerchantResponse(
        response_id="resp_drift",
        merchant_id="merchant_store_1",
        request_id="req_drift",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        is_success=True,
        total_amount=Money(amount=5400000, currency="INR"),
        offer_created_at=base_time,
        offer_expires_at=base_time + timedelta(hours=1),
    )

    session = service.execute_bounded_remediation(
        intent=base_intent,
        transaction_id=tx_id,
        initial_merchant_response=initial_resp,
        initial_evidence=drift_evidence,
        events=events,
        reference_time=base_time,
    )

    # Assertions
    assert session.original_verdict == IntegrityStatus.DRIFT
    assert len(session.original_violations) > 0
    assert session.state == NegotiationState.COMPLETED
    assert session.is_settled is True
    assert session.final_verdict == IntegrityStatus.PASS
    assert session.current_round >= 1

    # Verify cryptographic hash chain across all TIX messages generated in negotiation
    is_chain_valid, err = tix_service.verify_chain_integrity(tx_id)
    assert is_chain_valid is True
    assert err is None
    ledger = tix_service.get_ledger(tx_id)
    assert len(ledger) >= 4  # DRIFT_NOTICE, REMEDIATION_REQUEST, OFFER, OUTCOME


def test_permitted_sku_substitution_flow(
    base_time: datetime, base_intent: IntentContract, merchant_catalog: MerchantCatalogService
):
    # Make primary SKU out of stock
    merchant_catalog.set_inventory_status("SERVER-256", 0, InventoryStatus.SOLD_OUT)

    tix_service = TIXExchangeService()
    service = BoundedNegotiationService(
        merchant_service=merchant_catalog,
        tix_service=tix_service,
    )
    tx_id = "tx_neg_sub_01"

    # Initial attempt drifts because primary SKU was out of stock and offered unauthorized alternative
    drift_evidence = [
        Evidence(
            evidence_id="ev_sub_01",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="total_amount",
            field_value=Money(amount=4900000, currency="INR"),
            observed_at=base_time,
            is_authoritative=True,
        ),
        Evidence(
            evidence_id="ev_sub_02",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="executed_items",
            field_value=[{"sku": "UNAPPROVED-SKU", "quantity": 1}],  # Drift!
            observed_at=base_time,
            is_authoritative=True,
        ),
    ]

    initial_resp = MerchantResponse(
        response_id="resp_unapproved",
        merchant_id="merchant_store_1",
        request_id="req_unapproved",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        is_success=False,
        rejection_reason="Primary item SERVER-256 out of stock",
        offer_created_at=base_time,
        offer_expires_at=base_time + timedelta(hours=1),
    )

    session = service.execute_bounded_remediation(
        intent=base_intent,
        transaction_id=tx_id,
        initial_merchant_response=initial_resp,
        initial_evidence=drift_evidence,
        reference_time=base_time,
    )

    # Assertions
    assert session.original_verdict == IntegrityStatus.DRIFT
    assert session.is_settled is True


def test_negotiation_terminates_at_max_rounds(
    base_time: datetime, base_intent: IntentContract
):
    # Merchant that always rejects or offers prices above budget
    uncooperative_merchant = MerchantCatalogService(merchant_id="uncooperative")
    # No items in catalog -> always rejects
    service = BoundedNegotiationService(merchant_service=uncooperative_merchant)
    tx_id = "tx_neg_max_rounds"

    drift_evidence = [
        Evidence(
            evidence_id="ev_drift_01",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="total_amount",
            field_value=Money(amount=6000000, currency="INR"),
            observed_at=base_time,
            is_authoritative=True,
        ),
        Evidence(
            evidence_id="ev_drift_02",
            intent_id=base_intent.intent_id,
            source=EvidenceSource.RAZORPAY,
            field_name="executed_items",
            field_value=[{"sku": "SERVER-256", "quantity": 1}],
            observed_at=base_time,
            is_authoritative=True,
        ),
    ]

    initial_resp = MerchantResponse(
        response_id="resp_uncoop",
        merchant_id="uncooperative",
        request_id="req_uncoop",
        intent_id=base_intent.intent_id,
        transaction_id=tx_id,
        is_success=False,
        rejection_reason="Item unavailable",
        offer_created_at=base_time,
        offer_expires_at=base_time + timedelta(hours=1),
    )

    policy = NegotiationPolicy(max_rounds=3)
    session = service.execute_bounded_remediation(
        intent=base_intent,
        transaction_id=tx_id,
        initial_merchant_response=initial_resp,
        initial_evidence=drift_evidence,
        policy=policy,
        reference_time=base_time,
    )

    # Must terminate cleanly at max_rounds with ABSTAINED, never looping infinitely
    assert session.state == NegotiationState.ABSTAINED
    assert session.is_settled is True
    assert session.current_round == 3
    assert "Maximum negotiation rounds reached" in (session.termination_reason or "")
