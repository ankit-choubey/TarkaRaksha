"""
Unit tests for HeroTransactionOrchestrator (I22).

Tests:
1. Journey A: Happy path (without mutation)
2. Journey B: Full hero recovery flow (Detect -> Prove -> Repair -> Revalidate -> Execute -> Verify)
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.hero.contracts import (
    HeroStage,
    HeroTransactionRecord,
)
from backend.app.domain.models import (
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
)
from backend.app.services.hero.orchestrator import HeroTransactionOrchestrator
from backend.app.services.replay.contracts import ReplayVerdict


@pytest.fixture
def ref_time() -> datetime:
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def hero_intent(ref_time: datetime) -> IntentContract:
    return IntentContract(
        intent_id="intent_hero_ssd_01",
        issued_by="buyer_alice",
        items=[
            IntentItem(
                item_id="item_ssd_1",
                sku="SKU-SSD-1TB",
                name="1TB External SSD",
                quantity=1,
                unit_price=Money(amount=750000, currency="INR"),  # ₹7,500
                total_price=Money(amount=750000, currency="INR"),
            )
        ],
        max_total=Money(amount=800000, currency="INR"),  # ₹8,000 budget
        allowed_substitutions=["SKU-SSD-1TB-PRO"],
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=4),
    )


def test_journey_a_happy_path(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey A: Clean transaction flow without mutation.
    Verifies full lifecycle without drift triggers.
    """
    orchestrator = HeroTransactionOrchestrator()
    record = orchestrator.execute_hero_journey(
        intent=hero_intent,
        reference_time=ref_time,
        simulate_mutation=False,
    )

    assert isinstance(record, HeroTransactionRecord)
    assert record.current_stage == HeroStage.COMPLETED
    assert record.initial_integrity_result is not None
    assert record.initial_integrity_result.status == IntegrityStatus.PASS
    assert record.drift_integrity_result is None
    assert record.mrdp is None
    assert record.final_integrity_result.status == IntegrityStatus.PASS
    assert record.payment_result.status == "captured"
    assert record.tix_chain_valid is True
    assert record.replay_result.verdict == ReplayVerdict.MATCH
    assert len(record.lifecycle_digest) == 64


def test_journey_b_hero_recovery(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey B: Primary Hero Journey demonstrating the complete TarkaRaksha thesis:
    Detect -> Prove -> Repair -> Revalidate -> Execute -> Verify
    """
    orchestrator = HeroTransactionOrchestrator()
    record = orchestrator.execute_hero_journey(
        intent=hero_intent,
        reference_time=ref_time,
        simulate_mutation=True,
    )

    assert isinstance(record, HeroTransactionRecord)
    assert record.current_stage == HeroStage.COMPLETED

    # 1. Initial Pass
    assert record.initial_integrity_result is not None
    assert record.initial_integrity_result.status == IntegrityStatus.PASS

    # 2. Mutation & Drift Detection
    assert record.mutation is not None
    assert record.mutation["mutated_price_paise"] == 825000
    assert record.drift_integrity_result is not None
    assert record.drift_integrity_result.status == IntegrityStatus.DRIFT
    assert any("EconomicDrift" in v or "exceeds authorized max_total" in v for v in record.drift_integrity_result.violations)

    # 3. MRDP Generation
    assert record.mrdp is not None
    assert "EconomicDrift" in record.mrdp.violation
    assert record.mrdp.error_code == "ECONOMIC_AMOUNT_EXCEEDED"
    assert len(record.mrdp.proof_digest) == 64

    # 4. Drift Notice
    assert record.drift_notice is not None
    assert record.drift_notice.observed_total == 825000
    assert record.drift_notice.authorized_max == 800000
    assert record.drift_notice.mrdp_digest == record.mrdp.proof_digest

    # 5. Buyer Replan & Merchant Remediation
    assert record.replan_proposal is not None
    assert record.replan_proposal["requested_target_paise"] <= hero_intent.max_total.amount
    assert record.remediated_offer is not None
    assert record.remediated_offer["remediated_total_paise"] == 765000

    # 6. Revalidation
    assert record.revalidated_integrity_result is not None
    assert record.revalidated_integrity_result.status == IntegrityStatus.PASS

    # 7. Payment Execution & Binding
    assert record.binding_outcome is not None
    assert record.binding_outcome.is_valid is True
    assert record.payment_result is not None
    assert record.payment_result.status == "captured"

    # 8. Final Authoritative Verification
    assert record.final_integrity_result is not None
    assert record.final_integrity_result.status == IntegrityStatus.PASS

    # 9. Composed Observability & Audit Artifacts
    assert record.trace is not None
    assert len(record.trace.steps) == 8
    assert record.checkpoint_timeline is not None
    assert len(record.checkpoint_timeline.checkpoints) == 8
    assert record.sla_report is not None
    assert record.explanation is not None
    assert record.replay_result is not None
    assert record.replay_result.verdict == ReplayVerdict.MATCH
    assert record.tix_chain_valid is True
    assert record.tix_message_count >= 5

    # 10. Complete Stage History Sequence
    expected_stage_sequence = [
        HeroStage.INTENT_RECEIVED,
        HeroStage.BUYER_PROPOSED,
        HeroStage.MERCHANT_OFFERED,
        HeroStage.INITIAL_VALIDATION,
        HeroStage.INITIAL_PASS,
        HeroStage.MUTATION_INJECTED,
        HeroStage.DRIFT_DETECTED,
        HeroStage.MRDP_GENERATED,
        HeroStage.DRIFT_NOTIFIED,
        HeroStage.BUYER_REPLANNED,
        HeroStage.MERCHANT_REOFFERED,
        HeroStage.REVALIDATION,
        HeroStage.REVALIDATED_PASS,
        HeroStage.PAYMENT_EXECUTED,
        HeroStage.PAYMENT_VERIFIED,
        HeroStage.FINAL_INTEGRITY,
        HeroStage.COMPLETED,
    ]
    actual_sequence = [t.stage for t in record.stage_history]
    assert actual_sequence == expected_stage_sequence
