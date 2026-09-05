"""
Unit tests for Merchant Agent Domain Contracts (I4.1).
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.merchant import (
    BuyerCommerceRequest,
    BuyerItemRequest,
    CatalogItem,
    InventoryRecord,
    InventoryStatus,
    MerchantOfferItem,
    MerchantResponse,
    ShippingOption,
    TaxEstimate,
)
from backend.app.domain.models import Money


def test_catalog_item_creation():
    item = CatalogItem(
        sku="SKU-HEADSET-PRO",
        title="Wireless Noise Cancelling Headset",
        description="High fidelity audio headset with active noise cancellation",
        category="Audio",
        base_price=Money(amount=1500000, currency="INR"),
        tags=["wireless", "audio", "bluetooth"],
        attributes={"color": "Midnight Black", "warranty_months": 24},
    )
    assert item.sku == "SKU-HEADSET-PRO"
    assert item.base_price.amount == 1500000
    assert item.base_price.currency == "INR"
    assert item.is_active is True


def test_catalog_item_validation_rejects_empty_sku():
    with pytest.raises(ValueError, match="String identifier cannot be empty"):
        CatalogItem(
            sku="   ",
            title="Title",
            description="Desc",
            category="Cat",
            base_price=Money(amount=100, currency="INR"),
        )


def test_inventory_record_validation():
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    rec = InventoryRecord(
        sku="SKU-HEADSET-PRO",
        quantity_available=25,
        quantity_reserved=2,
        status=InventoryStatus.AVAILABLE,
        last_updated_at=now,
    )
    assert rec.quantity_available == 25
    assert rec.status == InventoryStatus.AVAILABLE

    # Negative quantity rejected
    with pytest.raises(ValueError, match="non-negative"):
        InventoryRecord(
            sku="SKU-HEADSET-PRO",
            quantity_available=-1,
            last_updated_at=now,
        )


def test_shipping_and_tax_contracts():
    ship = ShippingOption(
        option_id="ship-std",
        carrier="BlueDart",
        method_name="Standard Express",
        cost=Money(amount=25000, currency="INR"),
        estimated_days=2,
        guaranteed_days=3,
    )
    assert ship.cost.amount == 25000
    assert ship.estimated_days == 2

    tax = TaxEstimate(
        tax_type="GST",
        rate_bps=1800,
        amount=Money(amount=270000, currency="INR"),
        jurisdiction="KA",
    )
    assert tax.rate_bps == 1800
    assert tax.amount.amount == 270000


def test_buyer_commerce_request_and_merchant_response():
    t0 = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    req = BuyerCommerceRequest(
        request_id="req-001",
        buyer_agent_id="buyer-agent-alice",
        intent_id="intent-123",
        transaction_id="tx-456",
        items=[BuyerItemRequest(sku="SKU-HEADSET-PRO", quantity=1)],
        max_budget=Money(amount=2000000, currency="INR"),
        delivery_deadline_days=3,
        request_timestamp=t0,
    )
    assert req.buyer_agent_id == "buyer-agent-alice"
    assert len(req.items) == 1

    resp = MerchantResponse(
        response_id="resp-001",
        merchant_id="merchant-tech-mart",
        request_id=req.request_id,
        intent_id=req.intent_id,
        transaction_id=req.transaction_id,
        is_success=True,
        offer_id="off-001",
        items=[
            MerchantOfferItem(
                sku="SKU-HEADSET-PRO",
                title="Wireless Noise Cancelling Headset",
                quantity=1,
                unit_price=Money(amount=1500000, currency="INR"),
                total_price=Money(amount=1500000, currency="INR"),
            )
        ],
        subtotal=Money(amount=1500000, currency="INR"),
        discount=Money(amount=100000, currency="INR"),
        shipping=ShippingOption(
            option_id="ship-free",
            carrier="Internal",
            method_name="Free Standard",
            cost=Money(amount=0, currency="INR"),
            estimated_days=2,
        ),
        tax=TaxEstimate(
            tax_type="GST",
            rate_bps=1800,
            amount=Money(amount=252000, currency="INR"),
            jurisdiction="IN",
        ),
        total_amount=Money(amount=1652000, currency="INR"),
        offer_created_at=t0,
        offer_expires_at=t0 + timedelta(minutes=15),
        policy_version="merchant-policy-1.0.0",
        explanation="Offer calculated with standard customer discount",
    )
    assert resp.is_success is True
    assert resp.total_amount.amount == 1652000
    assert resp.inventory_status == InventoryStatus.AVAILABLE
