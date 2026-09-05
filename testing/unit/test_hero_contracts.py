"""
Unit tests for I22 Hero Transaction domain contracts.
"""
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.domain.hero.contracts import (
    HeroDriftNotice,
    HeroStage,
    HeroStageTransition,
    HeroTransactionRecord,
)
from backend.app.domain.models import (
    IntentContract,
    IntentItem,
    Money,
)


@pytest.fixture
def ref_time() -> datetime:
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_intent(ref_time: datetime) -> IntentContract:
    return IntentContract(
        intent_id="intent_hero_01",
        issued_by="buyer_alice",
        items=[
            IntentItem(
                item_id="item_ssd_1",
                sku="SKU-SSD-1TB",
                name="1TB External SSD",
                quantity=1,
                unit_price=Money(amount=750000, currency="INR"),
                total_price=Money(amount=750000, currency="INR"),
            )
        ],
        max_total=Money(amount=800000, currency="INR"),  # ₹8,000 max
        allowed_substitutions=["SKU-SSD-1TB-PRO"],
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=4),
    )


def test_hero_stage_enum_completeness():
    """Verify all 17 canonical stages exist in HeroStage enum."""
    expected_stages = [
        "INTENT_RECEIVED",
        "BUYER_PROPOSED",
        "MERCHANT_OFFERED",
        "INITIAL_VALIDATION",
        "INITIAL_PASS",
        "MUTATION_INJECTED",
        "DRIFT_DETECTED",
        "MRDP_GENERATED",
        "DRIFT_NOTIFIED",
        "BUYER_REPLANNED",
        "MERCHANT_REOFFERED",
        "REVALIDATION",
        "REVALIDATED_PASS",
        "PAYMENT_EXECUTED",
        "PAYMENT_VERIFIED",
        "FINAL_INTEGRITY",
        "COMPLETED",
    ]
    assert len(HeroStage) == 17
    for stage_name in expected_stages:
        assert HeroStage(stage_name) is not None


def test_hero_drift_notice_construction(ref_time: datetime):
    """Test valid construction and serialization of HeroDriftNotice."""
    notice = HeroDriftNotice(
        transaction_id="tx_hero_123",
        violated_constraint="TotalExceedsAuthorizedMax",
        authorized_max=800000,
        observed_total=825000,
        evidence_ids=["evi_offer_01"],
        mrdp_digest="a" * 64,
        remediation_required="Replan required: offer total exceeds authorized maximum of 800000 paise",
        timestamp=ref_time,
    )
    assert notice.transaction_id == "tx_hero_123"
    assert notice.violated_constraint == "TotalExceedsAuthorizedMax"
    assert notice.authorized_max == 800000
    assert notice.observed_total == 825000
    assert len(notice.mrdp_digest) == 64


def test_hero_transaction_record_lifecycle_digest(sample_intent: IntentContract, ref_time: datetime):
    """Test HeroTransactionRecord construction and deterministic lifecycle digest."""
    transition = HeroStageTransition(
        stage=HeroStage.INTENT_RECEIVED,
        timestamp=ref_time,
        description="Intent received and validated",
        stage_data={"buyer_id": "buyer_alice"},
    )
    record = HeroTransactionRecord(
        hero_transaction_id="hero_tx_001",
        transaction_id="tx_100",
        intent=sample_intent,
        current_stage=HeroStage.INTENT_RECEIVED,
        stage_history=[transition],
        buyer_id="buyer_alice",
        merchant_id="merchant_store_1",
        started_at=ref_time,
    )
    digest1 = record.compute_lifecycle_digest()
    digest2 = record.compute_lifecycle_digest()
    assert len(digest1) == 64
    assert digest1 == digest2
