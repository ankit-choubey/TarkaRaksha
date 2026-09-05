"""
Adversarial and Determinism tests for HeroTransactionOrchestrator (I22).

Covers:
- Journey C: Unsafe remediation attempt (budget expansion rejected)
- Journey D: Merchant authority abuse (merchant claims cannot override deterministic verification)
- Journey E: AI authority abuse (AI cannot overturn deterministic decisions)
- Journey F: Binding mismatch (tampered agent/order/tx rejected by I8)
- Journey G: Kill switch (KILLED safety gate halts execution)
- Journey H: UNKNOWN state preserved without conversion to PASS
- Journey I: Deterministic Replay (T13 side-effect-free audit matches perfectly)
- Determinism: Identical inputs + reference time produce identical lifecycle digests
- Secret Leakage: Zero sensitive secrets present in final records or traces
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.hero.contracts import (
    HeroStage,
    HeroTransactionRecord,
)
from backend.app.domain.kill_switch.contracts import (
    ExecutionBlockedError,
    KillSwitchState,
)
from backend.app.domain.models import (
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
)
from backend.app.services.evaluation import evaluate_integrity
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


def test_journey_c_unsafe_remediation_attempt(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey C: Unsafe Remediation Attempt.
    Attempt: A rogue or confused buyer agent attempts to resolve DRIFT by expanding
    the budget beyond the immutable authorized max (e.g. requesting ₹8,500).
    Result: Must be rejected by deterministic revalidation; cannot produce PASS.
    """
    # Verify that an offer beyond max_total evaluates to DRIFT
    unsafe_offer_ev = Evidence(
        evidence_id="evi_unsafe_replan",
        intent_id=hero_intent.intent_id,
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="total_amount",
        field_value=Money(amount=850000, currency="INR"),  # ₹8,500 > ₹8,000
        observed_at=ref_time + timedelta(seconds=40),
    )
    res = evaluate_integrity(
        contract=hero_intent,
        evidence_list=[unsafe_offer_ev],
        reference_time=ref_time + timedelta(seconds=45),
    )
    assert res.status == IntegrityStatus.DRIFT
    assert res.status != IntegrityStatus.PASS


def test_journey_d_merchant_authority_abuse(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey D: Merchant Authority Abuse.
    Attempt: Merchant agent falsely claims payment is captured and asserts PASS.
    Result: Merchant claims are MERCHANT_ATTESTED (70), not AUTHORITATIVE (100).
    Deterministic engine requires AUTHORITATIVE gateway evidence for financial truth.
    """
    merchant_claim_ev = Evidence(
        evidence_id="evi_merch_claim",
        intent_id=hero_intent.intent_id,
        source=EvidenceSource.MERCHANT,
        authority=EvidenceAuthority.MERCHANT_ATTESTED,
        field_name="payment_status",
        field_value="captured",
        observed_at=ref_time + timedelta(seconds=40),
    )
    # Total amount is missing from gateway
    res = evaluate_integrity(
        contract=hero_intent,
        evidence_list=[merchant_claim_ev],
        reference_time=ref_time + timedelta(seconds=45),
    )
    # Cannot be PASS without authoritative economic evidence
    assert res.status != IntegrityStatus.PASS


def test_journey_e_ai_authority_abuse(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey E: AI Authority Abuse.
    Attempt: AI explanation attempts to assert PASS or override verification findings.
    Result: AI output is strictly advisory; deterministic evaluation result remains untouched.
    """
    orchestrator = HeroTransactionOrchestrator()
    record = orchestrator.execute_hero_journey(
        intent=hero_intent,
        reference_time=ref_time,
        simulate_mutation=True,
    )
    # Deterministic final status is computed from verified rules, not AI
    assert record.final_integrity_result.status == IntegrityStatus.PASS
    assert record.explanation is not None
    # AI explanation cannot alter the recorded drift in history
    assert record.drift_integrity_result.status == IntegrityStatus.DRIFT


def test_journey_f_binding_mismatch(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey F: Binding Mismatch.
    Attempt: Agent ID in payment claim does not match the registered binding context.
    Result: Execution is immediately halted; RuntimeError raised with AGENT_MISMATCH.
    """
    orchestrator = HeroTransactionOrchestrator()
    with pytest.raises(RuntimeError) as exc_info:
        orchestrator.execute_hero_journey(
            intent=hero_intent,
            reference_time=ref_time,
            inject_binding_mismatch=True,
        )
    assert "Binding verification failed" in str(exc_info.value) or "AGENT_MISMATCH" in str(exc_info.value)


def test_journey_g_kill_switch_activation(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey G: Kill Switch.
    Attempt: Execute hero transaction while safety control is in KILLED state.
    Result: Fails closed immediately with ExecutionBlockedError before payment execution.
    """
    orchestrator = HeroTransactionOrchestrator()
    with pytest.raises(ExecutionBlockedError) as exc_info:
        orchestrator.execute_hero_journey(
            intent=hero_intent,
            reference_time=ref_time,
            inject_kill_switch_state=KillSwitchState.KILLED,
        )
    assert "KILLED" in str(exc_info.value)


def test_journey_h_unknown_state_preserved(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey H: UNKNOWN State Preservation.
    Attempt: Evaluate transaction with incomplete or unverified evidence.
    Result: UNKNOWN is preserved as first-class; never coerced into PASS.
    """
    # Empty evidence list
    res = evaluate_integrity(
        contract=hero_intent,
        evidence_list=[],
        reference_time=ref_time,
    )
    assert res.status == IntegrityStatus.UNKNOWN
    assert res.is_unknown is True
    assert res.is_pass is False


def test_journey_i_deterministic_replay_match(hero_intent: IntentContract, ref_time: datetime):
    """
    Journey I: Deterministic Replay.
    Verify that replaying the completed hero transaction produces ReplayVerdict.MATCH
    with zero discrepancies and pure functional execution.
    """
    orchestrator = HeroTransactionOrchestrator()
    record = orchestrator.execute_hero_journey(
        intent=hero_intent,
        reference_time=ref_time,
        simulate_mutation=True,
    )
    assert record.replay_result is not None
    assert record.replay_result.verdict == ReplayVerdict.MATCH
    assert len(record.replay_result.discrepancies) == 0


def test_hero_determinism_repeatability(hero_intent: IntentContract, ref_time: datetime):
    """
    Determinism Test (§35):
    Running the complete hero flow repeatedly with the same fixture and reference time
    must produce identical deterministic results and lifecycle digests.
    """
    orchestrator = HeroTransactionOrchestrator()

    record_1 = orchestrator.execute_hero_journey(
        intent=hero_intent,
        reference_time=ref_time,
        simulate_mutation=True,
    )

    record_2 = orchestrator.execute_hero_journey(
        intent=hero_intent,
        reference_time=ref_time,
        simulate_mutation=True,
    )

    # Identical lifecycle digest
    assert record_1.lifecycle_digest == record_2.lifecycle_digest
    assert len(record_1.lifecycle_digest) == 64

    # Identical stage sequence
    stages_1 = [t.stage for t in record_1.stage_history]
    stages_2 = [t.stage for t in record_2.stage_history]
    assert stages_1 == stages_2

    # Identical MRDP proof digest
    assert record_1.mrdp.proof_digest == record_2.mrdp.proof_digest

    # Identical final integrity decision
    assert record_1.final_integrity_result.status == record_2.final_integrity_result.status
    assert record_1.final_integrity_result.status == IntegrityStatus.PASS

    # Identical replay verdict
    assert record_1.replay_result.verdict == record_2.replay_result.verdict
    assert record_1.replay_result.verdict == ReplayVerdict.MATCH


def test_hero_zero_secret_leakage(hero_intent: IntentContract, ref_time: datetime):
    """
    Secret Leakage Adversarial Test (§31):
    Ensures that hero transaction records, stages, traces, and explanations
    do not leak credentials, API keys, or secrets.
    """
    orchestrator = HeroTransactionOrchestrator()
    record = orchestrator.execute_hero_journey(
        intent=hero_intent,
        reference_time=ref_time,
        simulate_mutation=True,
    )

    dump_str = record.model_dump_json()

    # Forbidden sensitive patterns
    forbidden_tokens = [
        "rzp_test_secret",
        "key_secret",
        "client_secret",
        "webhook_secret",
        "Bearer ",
        "authorization_header",
        "password",
        "private_key",
    ]

    for token in forbidden_tokens:
        assert token not in dump_str, f"Found sensitive secret token '{token}' in HeroTransactionRecord dump!"
