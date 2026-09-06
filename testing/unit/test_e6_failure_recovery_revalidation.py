"""
Comprehensive Test Suite for TarkaRaksha E6 — Failure -> Recovery -> Revalidation Hero Loop.

Covers:
1. Canonical E6 scenario setup: ₹50,000 budget, fixed SKU, 1 quantity, delivery constraint.
2. Initial valid merchant offer: Product ₹47,000 + Shipping ₹3,000 = Total ₹50,000 -> PASS.
3. Controlled economic drift: mutated total ₹55,000 > ₹50,000 -> DRIFT.
4. Cryptographic MRDP proof generation and structure.
5. Bounded buyer agent replan and merchant alternative within immutable authorization.
6. Deterministic revalidation: fresh evaluation -> PASS.
7. Payment execution strictly gated on successful revalidation.
8. Authoritative final restored hero message: "TRANSACTION RESTORED".
9. Kill-switch safety enforcement (I9): KILLED state aborts execution.
10. Protocol binding verification (I8): context mismatch rejected.
11. Historical replay compatibility: snapshot replay verdict MATCH.
12. Determinism and repeatability: identical digest across multiple runs.
13. Observability and evidence completeness: trace, checkpoints, SLA, AI explanation, TIX.
14. Adversarial tests:
    - Attempted budget increase during replan rejected.
    - Attempted SKU change rejected.
    - Attempted quantity escalation rejected.
    - Merchant self-declaration of PASS rejected by deterministic engine.
15. REST API endpoint execution: POST /api/v1/hero-transaction/run with scenario="e6".
"""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.hero import (
    HeroStage,
    HeroTransactionRecord,
    create_canonical_e6_intent,
)
from backend.app.domain.kill_switch.contracts import ExecutionBlockedError, KillSwitchState
from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityStatus,
    Money,
)
from backend.app.domain.evidence.extensions import MerchantOffer
from backend.app.main import app
from backend.app.services.evaluation import evaluate_integrity
from backend.app.services.hero.orchestrator import HeroTransactionOrchestrator
from backend.app.services.replay.contracts import ReplayVerdict


@pytest.fixture
def orchestrator() -> HeroTransactionOrchestrator:
    return HeroTransactionOrchestrator()


@pytest.fixture
def ref_time() -> datetime:
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


# ==============================================================================
# 1. CANONICAL E6 HERO JOURNEY TESTS (1 - 8)
# ==============================================================================

def test_e6_01_canonical_happy_path_pass(orchestrator, ref_time):
    """Happy path without mutation: ₹47,000 product + ₹3,000 shipping = ₹50,000 -> PASS."""
    intent = create_canonical_e6_intent(ref_time)
    record = orchestrator.execute_hero_journey(
        intent=intent,
        reference_time=ref_time,
        simulate_mutation=False,
        scenario="e6",
    )
    assert record.current_stage == HeroStage.COMPLETED
    assert record.initial_integrity_result is not None
    assert record.initial_integrity_result.status == IntegrityStatus.PASS
    assert record.drift_integrity_result is None
    assert record.mrdp is None
    assert record.revalidated_integrity_result is None
    assert record.final_integrity_result is not None
    assert record.final_integrity_result.status == IntegrityStatus.PASS
    assert record.payment_result is not None
    assert record.payment_result.status == "captured"
    assert record.payment_result.amount == Money(amount=5000000, currency="INR")
    assert "TRANSACTION VERIFIED" in (record.hero_message or "")


def test_e6_02_canonical_hero_loop_drift_recover_revalidate_pass(orchestrator, ref_time):
    """
    Full canonical E6 Hero Loop:
    ₹50,000 auth -> ₹47k+₹3k offer (PASS) -> ₹55k mutation (DRIFT) -> MRDP ->
    Bounded Recovery -> Valid Alternative (₹47k+₹3k) -> Revalidation (PASS) ->
    Payment Captured -> "TRANSACTION RESTORED".
    """
    intent = create_canonical_e6_intent(ref_time)
    record = orchestrator.execute_hero_journey(
        intent=intent,
        reference_time=ref_time,
        simulate_mutation=True,
        scenario="e6",
    )
    # 1. Completed
    assert record.current_stage == HeroStage.COMPLETED

    # 2. Stage history verification
    stage_names = [st.stage for st in record.stage_history]
    assert HeroStage.INTENT_RECEIVED in stage_names
    assert HeroStage.BUYER_PROPOSED in stage_names
    assert HeroStage.MERCHANT_OFFERED in stage_names
    assert HeroStage.INITIAL_PASS in stage_names
    assert HeroStage.MUTATION_INJECTED in stage_names
    assert HeroStage.DRIFT_DETECTED in stage_names
    assert HeroStage.MRDP_GENERATED in stage_names
    assert HeroStage.DRIFT_NOTIFIED in stage_names
    assert HeroStage.BUYER_REPLANNED in stage_names
    assert HeroStage.MERCHANT_REOFFERED in stage_names
    assert HeroStage.REVALIDATED_PASS in stage_names
    assert HeroStage.PAYMENT_EXECUTED in stage_names
    assert HeroStage.PAYMENT_VERIFIED in stage_names
    assert HeroStage.FINAL_INTEGRITY in stage_names
    assert HeroStage.COMPLETED in stage_names

    # 3. Initial Offer Verification
    assert record.initial_integrity_result.status == IntegrityStatus.PASS

    # 4. Drift Verification
    assert record.drift_integrity_result is not None
    assert record.drift_integrity_result.status == IntegrityStatus.DRIFT
    assert any("EconomicDrift" in v for v in record.drift_integrity_result.violations)
    assert record.mutation["mutated_price_paise"] == 5500000
    assert record.mutation["authorized_max_paise"] == 5000000

    # 5. MRDP Artifact
    assert record.mrdp is not None
    assert len(record.mrdp.proof_digest) == 64
    expected_amt = record.mrdp.expected.amount if hasattr(record.mrdp.expected, "amount") else record.mrdp.expected["amount"]
    observed_amt = record.mrdp.observed.amount if hasattr(record.mrdp.observed, "amount") else record.mrdp.observed["amount"]
    assert expected_amt == 5000000
    assert observed_amt == 5500000

    # 6. Revalidation Verification
    assert record.revalidated_integrity_result is not None
    assert record.revalidated_integrity_result.status == IntegrityStatus.PASS

    # 7. Payment Verification
    assert record.payment_result is not None
    assert record.payment_result.status == "captured"
    assert record.payment_result.amount == Money(amount=5000000, currency="INR")

    # 8. Authoritative Final Hero Message
    assert record.hero_message is not None
    assert "TRANSACTION RESTORED" in record.hero_message
    assert "Original authorization preserved" in record.hero_message
    assert "Payment verified" in record.hero_message
    assert "Recovery completed" in record.hero_message
    assert "Evidence recorded" in record.hero_message


def test_e6_03_authorization_preservation(orchestrator, ref_time):
    """Authorization invariants: max_total, SKU, quantity cannot be changed during recovery."""
    intent = create_canonical_e6_intent(ref_time)
    record = orchestrator.execute_hero_journey(intent=intent, reference_time=ref_time, simulate_mutation=True)

    # IntentContract immutable ceiling and fields
    assert record.intent.max_total.amount == 5000000
    assert record.intent.items[0].sku == "SKU-4K-MONITOR-01"
    assert record.intent.items[0].quantity == 1
    assert record.intent.allowed_substitutions == []

    # Recovery proposal respects original bounds
    assert record.replan_proposal["max_authorized_paise"] == 5000000
    assert record.replan_proposal["requested_target_paise"] <= 5000000

    # Remediated offer strictly satisfies authorized parameters
    assert record.remediated_offer["remediated_total_paise"] == 5000000


def test_e6_04_kill_switch_blocks_execution(orchestrator, ref_time):
    """Execution with KillSwitchState.KILLED aborts and does NOT execute payment."""
    intent = create_canonical_e6_intent(ref_time)
    with pytest.raises(ExecutionBlockedError) as exc_info:
        orchestrator.execute_hero_journey(
            intent=intent,
            reference_time=ref_time,
            inject_kill_switch_state=KillSwitchState.KILLED,
        )
    assert exc_info.value.state == KillSwitchState.KILLED


def test_e6_05_binding_mismatch_rejected(orchestrator, ref_time):
    """Protocol binding mismatch (rogue agent claim) is detected and rejected."""
    intent = create_canonical_e6_intent(ref_time)
    with pytest.raises(RuntimeError, match="Binding verification failed"):
        orchestrator.execute_hero_journey(
            intent=intent,
            reference_time=ref_time,
            inject_binding_mismatch=True,
        )


def test_e6_06_replay_compatibility(orchestrator, ref_time):
    """Replay engine reconstructs the transaction from recorded snapshot with MATCH verdict."""
    intent = create_canonical_e6_intent(ref_time)
    record = orchestrator.execute_hero_journey(intent=intent, reference_time=ref_time, simulate_mutation=True)
    assert record.replay_result is not None
    assert record.replay_result.verdict == ReplayVerdict.MATCH
    assert record.replay_result.discrepancies == []


def test_e6_07_determinism_and_repeatability(orchestrator, ref_time):
    """Multiple executions of canonical E6 scenario produce identical lifecycle digests."""
    intent = create_canonical_e6_intent(ref_time)
    run1 = orchestrator.execute_hero_journey(intent=intent, reference_time=ref_time, simulate_mutation=True)
    run2 = orchestrator.execute_hero_journey(intent=intent, reference_time=ref_time, simulate_mutation=True)

    assert run1.lifecycle_digest != ""
    assert len(run1.lifecycle_digest) == 64
    assert run1.lifecycle_digest == run2.lifecycle_digest


def test_e6_08_evidence_completeness_and_traceability(orchestrator, ref_time):
    """Verify trace, checkpoints, SLA report, explanation, and TIX are fully populated."""
    intent = create_canonical_e6_intent(ref_time)
    record = orchestrator.execute_hero_journey(intent=intent, reference_time=ref_time, simulate_mutation=True)

    # Trace
    assert record.trace is not None
    assert record.trace.transaction_id == f"tx_{intent.intent_id}"

    # Checkpoints
    assert record.checkpoint_timeline is not None
    assert len(record.checkpoint_timeline.checkpoints) > 0

    # SLA Report
    assert record.sla_report is not None
    assert record.sla_report.transaction_id == f"tx_{intent.intent_id}"

    # AI Explanation
    assert record.explanation is not None
    assert record.explanation.deterministic_decision == "PASS"

    # TIX ledger
    assert record.tix_message_count >= 5
    assert record.tix_chain_valid is True


# ==============================================================================
# 2. ADVERSARIAL TESTS (9 - 12)
# ==============================================================================

def test_e6_09_adversarial_recovery_attempts_to_increase_budget(ref_time):
    """Adversarial replan attempts to increase budget to ₹55,000 -> deterministic DRIFT."""
    intent = create_canonical_e6_intent(ref_time)
    # Rogue offer trying to demand ₹55,000
    rogue_offer = MerchantOffer(
        offer_id="off_rogue_budget",
        merchant_id="merchant_croma_store",
        sku="SKU-4K-MONITOR-01",
        quantity=1,
        unit_price=Money(amount=5200000, currency="INR"),
        discount=Money(amount=0, currency="INR"),
        shipping=Money(amount=300000, currency="INR"),
        tax=Money(amount=0, currency="INR"),
        total=Money(amount=5500000, currency="INR"),
        currency="INR",
        inventory_status="AVAILABLE",
        delivery_estimate="3 days",
        offer_created_at=ref_time,
        offer_expires_at=ref_time,
    )
    result = evaluate_integrity(
        contract=intent,
        evidence_list=rogue_offer.to_evidence(),
        events=[CanonicalEvent(event_id="e1", transaction_id="tx_1", intent_id=intent.intent_id, event_type="OFFER", timestamp=ref_time, sequence_number=1)],
        reference_time=ref_time,
    )
    assert result.status == IntegrityStatus.DRIFT
    assert any("EconomicDrift" in v for v in result.violations)


def test_e6_10_adversarial_recovery_attempts_sku_tampering(ref_time):
    """Adversarial replan attempts to substitute unauthorized cheaper/different SKU -> DRIFT."""
    intent = create_canonical_e6_intent(ref_time)
    rogue_offer = MerchantOffer(
        offer_id="off_rogue_sku",
        merchant_id="merchant_croma_store",
        sku="SKU-ROGUE-MONITOR-CHEAP",
        quantity=1,
        unit_price=Money(amount=4700000, currency="INR"),
        discount=Money(amount=0, currency="INR"),
        shipping=Money(amount=300000, currency="INR"),
        tax=Money(amount=0, currency="INR"),
        total=Money(amount=5000000, currency="INR"),
        currency="INR",
        inventory_status="AVAILABLE",
        delivery_estimate="3 days",
        offer_created_at=ref_time,
        offer_expires_at=ref_time,
    )
    result = evaluate_integrity(
        contract=intent,
        evidence_list=rogue_offer.to_evidence(),
        events=[CanonicalEvent(event_id="e1", transaction_id="tx_1", intent_id=intent.intent_id, event_type="OFFER", timestamp=ref_time, sequence_number=1)],
        reference_time=ref_time,
    )
    assert result.status == IntegrityStatus.DRIFT
    assert any("UnauthorizedSKU" in v for v in result.violations)


def test_e6_11_adversarial_recovery_attempts_quantity_escalation(ref_time):
    """Adversarial replan attempts to change quantity from 1 to 2 -> DRIFT."""
    intent = create_canonical_e6_intent(ref_time)
    rogue_offer = MerchantOffer(
        offer_id="off_rogue_qty",
        merchant_id="merchant_croma_store",
        sku="SKU-4K-MONITOR-01",
        quantity=2,
        unit_price=Money(amount=2350000, currency="INR"),
        discount=Money(amount=0, currency="INR"),
        shipping=Money(amount=300000, currency="INR"),
        tax=Money(amount=0, currency="INR"),
        total=Money(amount=5000000, currency="INR"),
        currency="INR",
        inventory_status="AVAILABLE",
        delivery_estimate="3 days",
        offer_created_at=ref_time,
        offer_expires_at=ref_time,
    )
    result = evaluate_integrity(
        contract=intent,
        evidence_list=rogue_offer.to_evidence(),
        events=[CanonicalEvent(event_id="e1", transaction_id="tx_1", intent_id=intent.intent_id, event_type="OFFER", timestamp=ref_time, sequence_number=1)],
        reference_time=ref_time,
    )
    assert result.status == IntegrityStatus.DRIFT
    assert any("QuantityMismatch" in v for v in result.violations)


def test_e6_12_adversarial_merchant_self_declares_pass_without_evidence(ref_time):
    """Merchant claim of 'ALL_VALID' with missing payment amount evidence evaluates to UNKNOWN, not PASS."""
    intent = create_canonical_e6_intent(ref_time)
    merchant_claim = Evidence(
        evidence_id="evi_merch_claim_pass",
        intent_id=intent.intent_id,
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="merchant_claim",
        field_value={"status": "PASS", "certified": True},
        observed_at=ref_time,
    )
    result = evaluate_integrity(
        contract=intent,
        evidence_list=[merchant_claim],
        events=[],
        reference_time=ref_time,
    )
    # Missing total_amount evidence results in UNKNOWN
    assert result.status == IntegrityStatus.UNKNOWN


# ==============================================================================
# 3. REST API ENDPOINT INTEGRATION (13)
# ==============================================================================

def test_e6_13_post_hero_transaction_run_api_scenario_e6():
    """POST /api/v1/hero-transaction/run with scenario='e6' executes canonical E6 loop via REST API."""
    client = TestClient(app)
    response = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6", "simulate_mutation": True})
    assert response.status_code == 200
    data = response.json()
    assert data["current_stage"] == "COMPLETED"
    assert data["intent"]["max_total"]["amount"] == 5000000
    assert data["mutation"]["mutated_price_paise"] == 5500000
    assert data["drift_integrity_result"]["status"] == "DRIFT"
    assert data["revalidated_integrity_result"]["status"] == "PASS"
    assert data["final_integrity_result"]["status"] == "PASS"
    assert data["payment_result"]["status"] == "captured"
    assert "TRANSACTION RESTORED" in data["hero_message"]


def test_e6_14_explicit_scenario_isolation(orchestrator, ref_time):
    """Explicit scenario parameter controls whether E6 (₹50k) or I22 default (₹8k) logic executes."""
    intent_e6 = create_canonical_e6_intent(ref_time)
    
    # 1. Explicit scenario="e6"
    rec_e6 = orchestrator.execute_hero_journey(
        intent=intent_e6,
        reference_time=ref_time,
        simulate_mutation=True,
        scenario="e6",
    )
    assert rec_e6.mutation["mutated_price_paise"] == 5500000
    assert rec_e6.mutation["authorized_max_paise"] == 5000000
    assert rec_e6.final_integrity_result.status == IntegrityStatus.PASS

    # 2. REST API explicit scenario="default" runs default I22 behavior
    client = TestClient(app)
    resp_default = client.post("/api/v1/hero-transaction/run", json={"scenario": "default", "simulate_mutation": True})
    assert resp_default.status_code == 200
    data_def = resp_default.json()
    assert data_def["intent"]["max_total"]["amount"] == 800000
    assert data_def["mutation"]["mutated_price_paise"] == 825000

