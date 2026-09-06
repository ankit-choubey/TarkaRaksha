"""
Canonical E6 Hero Intent Definition: Failure -> Recovery -> Revalidation Hero Loop.

Scenario constraints (per E6 Product Specification):
- Maximum authorized total: ₹50,000 (5,000,000 paise)
- SKU: fixed "SKU-4K-MONITOR-01"
- Quantity: 1
- Currency: INR
- Delivery constrained: max shipping ₹3,000 (300,000 paise)
- Product baseline: ₹47,000 (4,700,000 paise)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.models.money import Money


def create_canonical_e6_intent(reference_time: Optional[datetime] = None) -> IntentContract:
    """
    Constructs the immutable canonical IntentContract for E6 hero demonstration.
    Authorized ceiling: ₹50,000.00 INR (5,000,000 paise).
    Product allocation: ₹47,000.00 INR (4,700,000 paise).
    Shipping ceiling: ₹3,000.00 INR (300,000 paise).
    """
    ref_time = reference_time or datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id=f"intent_hero_e6_{int(ref_time.timestamp())}",
        issued_by="buyer_agent_alice",
        items=[
            IntentItem(
                item_id="item_monitor_4k_01",
                sku="SKU-4K-MONITOR-01",
                name="UltraHD 4K 27-inch Monitor",
                quantity=1,
                unit_price=Money(amount=4700000, currency="INR"),
                total_price=Money(amount=4700000, currency="INR"),
            )
        ],
        max_total=Money(amount=5000000, currency="INR"),
        currency="INR",
        allow_partial=False,
        allowed_substitutions=[],
        max_successful_captures=1,
        max_retries=3,
        contract_version="1.0.0",
        policy_version="1.0.0",
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=4),
    )
