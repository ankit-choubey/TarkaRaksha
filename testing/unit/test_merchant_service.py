"""
Unit tests for Deterministic Catalog, Inventory, and Offer Service (I4.3).
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.merchant import (
    BuyerCommerceRequest,
    BuyerItemRequest,
    CommerceCapabilityType,
    InventoryStatus,
)
from backend.app.domain.models import Money
from backend.app.services.merchant import MerchantCatalogService


@pytest.fixture
def merchant_svc():
    return MerchantCatalogService()


def test_merchant_catalog_lookup(merchant_svc):
    item = merchant_svc.get_catalog_item("SKU-BOOK-001")
    assert item is not None
    assert item.title == "Agentic Systems & Deterministic Control"
    assert item.base_price.amount == 500000

    inv = merchant_svc.get_inventory_record("SKU-BOOK-001")
    assert inv is not None
    assert inv.quantity_available == 50
    assert inv.status == InventoryStatus.AVAILABLE


def test_deterministic_offer_generation(merchant_svc):
    ref_time = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    req = BuyerCommerceRequest(
        request_id="req-test-1",
        buyer_agent_id="buyer-1",
        intent_id="intent-1",
        transaction_id="tx-1",
        items=[BuyerItemRequest(sku="SKU-BOOK-001", quantity=1)],
        preferred_shipping_id="ship-standard",
    )

    resp1 = merchant_svc.process_buyer_request(req, discount_percentage_bps=1000, reference_time=ref_time)
    resp2 = merchant_svc.process_buyer_request(req, discount_percentage_bps=1000, reference_time=ref_time)

    assert resp1.is_success is True
    assert resp2.is_success is True
    # Invariant: same inputs -> exact same output
    assert resp1.subtotal == resp2.subtotal
    assert resp1.discount == resp2.discount
    assert resp1.shipping == resp2.shipping
    assert resp1.tax == resp2.tax
    assert resp1.total_amount == resp2.total_amount

    # Verify math: Subtotal: ₹5000 (500000). Discount 10%: ₹500 (50000). Shipping: ₹100 (10000).
    # Taxable base: 500000 - 50000 + 10000 = 460000. Tax (18%): 82800.
    # Total: 460000 + 82800 = 542800.
    assert resp1.subtotal.amount == 500000
    assert resp1.discount.amount == 50000
    assert resp1.shipping.cost.amount == 10000
    assert resp1.tax.amount.amount == 82800
    assert resp1.total_amount.amount == 542800


def test_offer_alternative_proposed_when_sold_out(merchant_svc):
    ref_time = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    # Set primary mouse out of stock
    merchant_svc.set_inventory_status("SKU-MOUSE-001", quantity=0)

    req = BuyerCommerceRequest(
        request_id="req-mouse",
        buyer_agent_id="buyer-1",
        intent_id="intent-2",
        transaction_id="tx-2",
        items=[BuyerItemRequest(sku="SKU-MOUSE-001", quantity=1)],
    )

    resp = merchant_svc.process_buyer_request(req, reference_time=ref_time)
    assert resp.is_success is False
    assert resp.inventory_status == InventoryStatus.SOLD_OUT
    assert len(resp.alternatives) == 1
    assert resp.alternatives[0]["sku"] == "SKU-MOUSE-ALT"


def test_conversion_to_evidence_merchant_offer(merchant_svc):
    ref_time = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    req = BuyerCommerceRequest(
        request_id="req-convert",
        buyer_agent_id="buyer-1",
        intent_id="intent-3",
        transaction_id="tx-3",
        items=[BuyerItemRequest(sku="SKU-BOOK-001", quantity=1)],
    )
    resp = merchant_svc.process_buyer_request(req, reference_time=ref_time)
    offer = merchant_svc.convert_response_to_merchant_offer(resp)

    assert offer is not None
    assert offer.sku == "SKU-BOOK-001"
    assert offer.total == resp.total_amount

    # Convert to TarkaRaksha evidence records (offer object, total_amount, executed_items)
    ev_records = offer.to_evidence()
    assert len(ev_records) == 3
    assert all(r.source.value == "MERCHANT" for r in ev_records)
    assert all(r.authority.value == "MERCHANT_ATTESTED" for r in ev_records)


def test_fulfillment_deadline_unmet_rejected(merchant_svc):
    ref_time = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    # Standard shipping is 3 days; buyer requires delivery in 1 day
    req = BuyerCommerceRequest(
        request_id="req-deadline",
        buyer_agent_id="buyer-1",
        intent_id="intent-4",
        transaction_id="tx-4",
        items=[BuyerItemRequest(sku="SKU-BOOK-001", quantity=1)],
        preferred_shipping_id="ship-standard",
        delivery_deadline_days=1,
    )
    resp = merchant_svc.process_buyer_request(req, reference_time=ref_time)
    assert resp.is_success is False
    assert "Cannot fulfill within deadline" in resp.rejection_reason
