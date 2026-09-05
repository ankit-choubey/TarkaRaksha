"""
Unit tests for Merchant Integrity verification in TarkaRaksha (I4).
Covers offer expiry, inventory state transitions, and fulfillment delivery integrity.
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.models.money import Money
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.merchant.contracts import (
    FulfillmentTerms,
    InventoryStatus,
    MerchantOffer,
    MerchantOfferItem,
    ShippingOption,
    TaxEstimate,
)
from backend.app.domain.merchant.integrity import (
    MerchantIntegrityVerifier,
    OfferVerificationResult,
    OfferVerificationStatus,
)


@pytest.fixture
def sample_offer():
    created_at = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    expires_at = created_at + timedelta(minutes=15)
    
    return MerchantOffer(
        response_id="resp-test-123",
        merchant_id="merch_acme_corp",
        request_id="req-test-123",
        intent_id="intent-test-123",
        transaction_id="tx-test-123",
        is_success=True,
        offer_id="off_test_123",
        items=[
            MerchantOfferItem(
                sku="SKU-PHONE-1",
                title="Pixel 9 Pro",
                quantity=1,
                unit_price=Money(amount=7999900, currency="INR"),
                total_price=Money(amount=7999900, currency="INR"),
            )
        ],
        subtotal=Money(amount=7999900, currency="INR"),
        shipping=ShippingOption(
            option_id="ship_express",
            method_name="Express Courier",
            carrier="BlueDart",
            cost=Money(amount=15000, currency="INR"),
            estimated_days=2,
        ),
        tax=TaxEstimate(
            tax_type="GST",
            rate_bps=1800,
            amount=Money(amount=1442682, currency="INR"),
            jurisdiction="IN",
        ),
        total_amount=Money(amount=9457582, currency="INR"),
        inventory_status=InventoryStatus.AVAILABLE,
        estimated_delivery_days=2,
        offer_created_at=created_at,
        offer_expires_at=expires_at,
    )



def test_offer_expiry_valid_within_window(sample_offer):
    # Current time is 5 minutes after offer creation (valid)
    eval_time = datetime(2026, 9, 5, 12, 5, tzinfo=timezone.utc)
    res = MerchantIntegrityVerifier.verify_offer_expiry(sample_offer, current_time=eval_time)

    assert res.is_valid is True
    assert res.status == OfferVerificationStatus.VALID
    assert res.integrity_status == IntegrityStatus.PASS
    assert res.action_recommended == "PROCEED"
    assert res.rule_result is not None
    assert res.rule_result.is_pass is True


def test_offer_expiry_rejected_when_stale(sample_offer):
    # Current time is 20 minutes after offer creation (expired by 5 minutes)
    eval_time = datetime(2026, 9, 5, 12, 20, tzinfo=timezone.utc)
    res = MerchantIntegrityVerifier.verify_offer_expiry(sample_offer, current_time=eval_time)

    assert res.is_valid is False
    assert res.status == OfferVerificationStatus.EXPIRED
    assert res.integrity_status == IntegrityStatus.DRIFT
    assert res.action_recommended == "REQUEST_REFRESH"
    assert res.violation == "EXPIRED_OFFER_REJECTED"
    assert res.rule_result is not None
    assert res.rule_result.is_drift is True


def test_inventory_integrity_valid_stock(sample_offer):
    # Available stock = 10, required = 1
    res = MerchantIntegrityVerifier.verify_inventory_integrity(
        offer=sample_offer,
        current_stock=10,
        required_quantity=1,
        authoritative_evidence_available=True,
    )

    assert res.is_valid is True
    assert res.status == OfferVerificationStatus.VALID
    assert res.integrity_status == IntegrityStatus.PASS
    assert res.action_recommended == "PROCEED"


def test_inventory_integrity_detects_stock_depletion(sample_offer):
    # Stock depleted to 0 (sold out)
    res = MerchantIntegrityVerifier.verify_inventory_integrity(
        offer=sample_offer,
        current_stock=0,
        required_quantity=1,
        authoritative_evidence_available=True,
    )

    assert res.is_valid is False
    assert res.status == OfferVerificationStatus.INVENTORY_DEPLETED
    assert res.integrity_status == IntegrityStatus.DRIFT
    assert res.action_recommended == "RE_EVALUATE_INVENTORY"
    assert res.violation == "INVENTORY_STATE_DRIFT"
    assert res.expected == ">= 1"
    assert res.observed == 0


def test_inventory_integrity_unknown_when_evidence_missing(sample_offer):
    # Authoritative stock evidence is missing
    res = MerchantIntegrityVerifier.verify_inventory_integrity(
        offer=sample_offer,
        current_stock=None,
        authoritative_evidence_available=False,
    )

    assert res.is_valid is False
    assert res.integrity_status == IntegrityStatus.UNKNOWN
    assert res.action_recommended == "VERIFY_INVENTORY_AUTHORITATIVE"
    assert res.violation == "INSUFFICIENT_STOCK_EVIDENCE"


def test_fulfillment_integrity_valid_delivery_window(sample_offer):
    # Buyer allows up to 3 days, offer delivers in 2 days
    res = MerchantIntegrityVerifier.verify_fulfillment_integrity(
        offer=sample_offer,
        buyer_max_delivery_days=3,
        buyer_required_carrier="BlueDart",
    )

    assert res.is_valid is True
    assert res.status == OfferVerificationStatus.VALID
    assert res.integrity_status == IntegrityStatus.PASS
    assert res.action_recommended == "PROCEED"


def test_fulfillment_integrity_temporal_drift(sample_offer):
    # Buyer requires delivery within 1 day, offer delivers in 2 days
    res = MerchantIntegrityVerifier.verify_fulfillment_integrity(
        offer=sample_offer,
        buyer_max_delivery_days=1,
    )

    assert res.is_valid is False
    assert res.status == OfferVerificationStatus.FULFILLMENT_BREACH
    assert res.integrity_status == IntegrityStatus.DRIFT
    assert res.action_recommended == "RENEGOTIATE_FULFILLMENT"
    assert res.violation == "TEMPORAL_FULFILLMENT_DRIFT"
    assert res.expected == 1
    assert res.observed == 2


def test_fulfillment_integrity_carrier_mismatch(sample_offer):
    # Buyer explicitly demands FedEx, offer provides BlueDart
    res = MerchantIntegrityVerifier.verify_fulfillment_integrity(
        offer=sample_offer,
        buyer_required_carrier="FedEx",
    )

    assert res.is_valid is False
    assert res.status == OfferVerificationStatus.FULFILLMENT_BREACH
    assert res.integrity_status == IntegrityStatus.DRIFT
    assert res.action_recommended == "RENEGOTIATE_FULFILLMENT"
    assert res.violation == "CARRIER_MISMATCH"


def test_verify_all_comprehensive(sample_offer):
    eval_time = datetime(2026, 9, 5, 12, 5, tzinfo=timezone.utc)
    results = MerchantIntegrityVerifier.verify_all(
        offer=sample_offer,
        current_time=eval_time,
        buyer_max_delivery_days=3,
        buyer_required_carrier="BlueDart",
        current_stock=5,
        required_quantity=1,
    )

    assert len(results) == 3
    assert all(r.is_valid for r in results)
    assert all(r.integrity_status == IntegrityStatus.PASS for r in results)
