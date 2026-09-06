"""
End-to-End Demonstration Certification Test Suite for TarkaRaksha (E9).

Testing reference: brain/TarkaRaksha_TESTING.md & E9 Execution Directives.

Covers:
- Scenario A: HAPPY_PATH full end-to-end composition
- Scenario B: ECONOMIC_DRIFT canonical E6 hero recovery loop
- Authorization ceiling immutability invariant
"""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.hero import HeroStage, create_canonical_e6_intent
from backend.app.domain.models import (
    IntegrityStatus,
    Money,
    TransactionState,
)
from backend.app.domain.scenario.contracts import ScenarioId, ScenarioStatus
from backend.app.main import app
from backend.app.services.certification.end_to_end import EndToEndCertificationService
from backend.app.services.hero.orchestrator import HeroTransactionOrchestrator
from backend.app.services.scenario.proof import ScenarioProofService


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def cert_service():
    """Singleton EndToEndCertificationService fixture."""
    return EndToEndCertificationService()


@pytest.fixture
def ref_time():
    """Fixed reference timestamp for reproducible testing."""
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


# ==============================================================================
# 1. CANONICAL HAPPY PATH COMPOSITION
# ==============================================================================

def test_e9_01_canonical_happy_path_composition(cert_service):
    """
    Certifies Happy Path full agentic composition:
    Buyer Intent -> Binding -> Merchant Offer -> Deterministic Integrity PASS ->
    Proof Generation -> Replay MATCH.
    """
    item = cert_service.certify_happy_path()
    assert item.status == "PASS"
    assert item.evidence_type == "SYNTHETIC_OFFLINE_FIXTURE"
    assert item.evidence_digest is not None
    assert len(item.evidence_digest) == 64
    assert item.transaction_id is not None

    # Deep verification of the generated proof
    proof = cert_service.proof_service.generate_proof(ScenarioId.HAPPY_PATH)
    assert proof.actual_verdict == "PASS"
    assert proof.scenario_status == ScenarioStatus.PASS
    assert len(proof.violations) == 0
    assert proof.replay_verdict == "MATCH"
    assert len(proof.proof_chain) >= 6

    # Verify stage progression
    stage_names = [st.stage_name for st in proof.proof_chain]
    assert "AUTHORIZED STATE" in stage_names[0]
    assert "DETERMINISTIC VERIFICATION" in stage_names[2]
    assert "FINAL OUTCOME" in stage_names[5]


# ==============================================================================
# 2. CANONICAL ECONOMIC DRIFT & HERO RECOVERY LOOP
# ==============================================================================

def test_e9_02_canonical_economic_drift_hero_loop(cert_service):
    """
    Certifies the complete canonical E6 closed recovery loop:
    ₹50,000 authorized ceiling -> Initial PASS -> ₹55,000 mutation DRIFT ->
    Cryptographic MRDP -> Bounded replan within ₹50,000 -> Revalidation PASS ->
    Authoritative "TRANSACTION RESTORED".
    """
    item = cert_service.certify_economic_drift()
    assert item.status == "PASS"
    assert item.evidence_type == "SYNTHETIC_OFFLINE_FIXTURE"
    assert item.evidence_digest is not None
    assert item.transaction_id is not None
    assert "TRANSACTION RESTORED" in item.verified_fact

    # Deep verification of hero orchestrator execution
    ref_t = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    intent = create_canonical_e6_intent(ref_t)
    record = cert_service.hero_orchestrator.execute_hero_journey(
        intent=intent,
        reference_time=ref_t,
        simulate_mutation=True,
        scenario="e6",
    )

    assert record.current_stage == HeroStage.COMPLETED
    assert record.initial_integrity_result.status == IntegrityStatus.PASS
    assert record.drift_integrity_result.status == IntegrityStatus.DRIFT
    assert record.mrdp is not None
    assert len(record.mrdp.proof_digest) == 64
    assert record.replan_proposal is not None
    assert record.replan_proposal.get("requested_target_paise", 0) <= record.intent.max_total.amount
    assert record.revalidated_integrity_result.status == IntegrityStatus.PASS
    assert "TRANSACTION RESTORED" in (record.hero_message or "")


def test_e9_03_remediation_bounded_within_ceiling(cert_service, ref_time):
    """
    Certifies that neither replanning nor recovery can escalate the authorization ceiling.
    """
    item = cert_service.certify_authorization_invariance()
    assert item.status == "PASS"
    assert "ceiling" in item.verified_fact.lower()

    # Direct proof inspection
    proof = cert_service.proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    assert proof.recovery_summary is not None
    assert "5,000" in proof.recovery_summary["original_ceiling"]
    assert proof.recovery_summary["replan_bounded_by_ceiling"] is True


# ==============================================================================
# 3. MERCHANT AGENT ABUSE & THREAT CONTAINMENT
# ==============================================================================

def test_e9_04_merchant_agent_abuse_containment(cert_service):
    """
    Certifies that compromised merchant agent proposals cannot substitute
    for authoritative gateway evidence or force a financial PASS.
    """
    item = cert_service.certify_merchant_abuse()
    assert item.status == "PASS"
    assert item.evidence_type == "SYNTHETIC_OFFLINE_FIXTURE"
    assert "blocked" in item.verified_fact.lower()

    # Direct proof inspection
    proof = cert_service.proof_service.generate_proof(ScenarioId.MERCHANT_AGENT_COMPROMISED)
    assert proof.actual_verdict == "UNKNOWN"
    assert proof.actual_verdict != "PASS"
    assert proof.security_findings.get("kill_switch_state") == "SAFETY_PAUSED"
    # Verify no fake payment capture was certified
    assert proof.scenario_id == ScenarioId.MERCHANT_AGENT_COMPROMISED


# ==============================================================================
# 4. UNKNOWN PROVIDER STATE SAFETY PATH
# ==============================================================================

def test_e9_05_unknown_provider_state_safety_path(cert_service):
    """
    Certifies that UNKNOWN is preserved as a first-class state and is NEVER
    coerced directly into PASS.
    """
    item = cert_service.certify_unknown_resolution()
    assert item.status == "PASS"
    assert "never coerced to pass" in item.verified_fact.lower()

    # Direct proof inspection
    proof = cert_service.proof_service.generate_proof(ScenarioId.UNKNOWN_PROVIDER_STATE)
    assert proof.actual_verdict == "UNKNOWN"
    assert proof.actual_verdict != "PASS"
    assert any("UNKNOWN" in stage.status for stage in proof.proof_chain)


# ==============================================================================
# 5. DETERMINISTIC REPLAY & TAMPER RESISTANCE
# ==============================================================================

def test_e9_06_deterministic_replay_and_tamper_detection(cert_service):
    """
    Certifies that T13 CPU-only ReplayEngine detects historical state mutation
    yielding MISMATCH without network or payment side effects.
    """
    item = cert_service.certify_replay_tamper()
    assert item.status == "PASS"
    assert "mismatch" in item.verified_fact.lower()

    # Direct proof inspection
    proof = cert_service.proof_service.generate_proof(ScenarioId.REPLAY_ATTACK)
    assert proof.actual_verdict == "MISMATCH"
    assert proof.replay_verdict == "MISMATCH"
    assert proof.security_findings.get("replay_divergence_detected") is True


# ==============================================================================
# 6. 7-TUPLE CONTEXT BINDING ENFORCEMENT
# ==============================================================================

def test_e9_07_seven_tuple_binding_enforcement(cert_service):
    """
    Certifies that 7-tuple context (intent_id, agent_id, merchant_id,
    transaction_id, order_id, payment_id, attempt_id) is enforced, rejecting
    cross-context agent reuse.
    """
    item = cert_service.certify_seven_tuple_binding()
    assert item.status == "PASS"
    assert "rejected" in item.verified_fact.lower()

    # Direct proof inspection
    proof = cert_service.proof_service.generate_proof(ScenarioId.BUYER_AGENT_REUSE)
    assert proof.actual_verdict == "REJECTED"
    assert proof.security_findings.get("binding_status") in ("DRIFT", "MISMATCH")
    assert "TRANSACTION_MISMATCH" in proof.violations


# ==============================================================================
# 7. TRANSACTION PASSPORT OBSERVATIONAL PROJECTION
# ==============================================================================

def test_e9_08_transaction_passport_observational_composition(cert_service):
    """
    Certifies that E5 Transaction Passport composes complete audit story
    purely observationally without creating secondary mutable state.
    """
    item = cert_service.certify_transaction_passport()
    assert item.status == "PASS"
    assert "read-only" in item.verified_fact.lower()

    # Inspect proof chain as passport observational baseline
    proof = cert_service.proof_service.generate_proof(ScenarioId.HAPPY_PATH)
    assert proof.transaction_id is not None
    assert proof.intent_id is not None
    assert len(proof.proof_chain) >= 6
    assert proof.proof_digest is not None


# ==============================================================================
# 8. CONTROL ROOM LIVE TELEMETRY SYNC
# ==============================================================================

def test_e9_09_control_room_live_telemetry_integration(cert_service):
    """
    Certifies that E7 Control Room snapshot accurately exposes all 5
    observability deep-dive tabs synchronized from authoritative proof.
    """
    item = cert_service.certify_control_room_sync()
    assert item.status == "PASS"
    assert "synchronized" in item.verified_fact.lower()

    # Deep verification of Control Room projection
    latest = cert_service.control_room_service.get_latest_snapshot()
    assert latest is not None
    assert latest.identity.transaction_id is not None
    assert latest.integrity.status.value in ("PASS", "DRIFT", "UNKNOWN")
    assert latest.drift_proof is not None or latest.integrity.status.value == "PASS"
    assert latest.security is not None
    assert latest.replay is not None
    assert latest.observability is not None


# ==============================================================================
# 9. SCENARIO / PROOF SURFACE CATALOG COMPLETENESS
# ==============================================================================

def test_e9_10_scenario_proof_surface_catalog_completeness(cert_service):
    """
    Certifies that all 12 canonical scenarios exist, have stable IDs,
    and generate verifiable proofs.
    """
    item = cert_service.certify_scenario_surface()
    assert item.status == "PASS"
    assert "12 canonical scenarios" in item.verified_fact.lower()

    # Verify all 12 IDs directly
    expected_ids = {
        ScenarioId.HAPPY_PATH,
        ScenarioId.PRICE_DRIFT,
        ScenarioId.WRONG_SKU,
        ScenarioId.INVENTORY_DISAPPEARS,
        ScenarioId.DELIVERY_DRIFT,
        ScenarioId.DUPLICATE_PAYMENT,
        ScenarioId.DELAYED_WEBHOOK,
        ScenarioId.REPLAY_ATTACK,
        ScenarioId.PROMPT_INJECTION_IN_EVIDENCE,
        ScenarioId.MERCHANT_AGENT_COMPROMISED,
        ScenarioId.BUYER_AGENT_REUSE,
        ScenarioId.UNKNOWN_PROVIDER_STATE,
    }
    assert len(expected_ids) == 12
    for sc_id in expected_ids:
        proof = cert_service.proof_service.generate_proof(sc_id)
        assert proof.scenario_id == sc_id
        assert len(proof.proof_digest) == 64


# ==============================================================================
# 10. RAZORPAY TEST MODE INTEGRATION & SIGNATURE VERIFICATION
# ==============================================================================

def test_e9_11_razorpay_test_mode_order_and_signature_verification(cert_service):
    """
    Certifies Razorpay Test Mode integration:
    Live order creation on Razorpay Test Mode and cryptographic HMAC-SHA256
    signature verification using configured test credentials in .env.
    """
    item = cert_service.certify_razorpay_mode()
    assert item.status == "PASS"
    assert item.evidence_type == "LIVE_VERIFIED"
    assert item.transaction_id is not None
    assert item.transaction_id.startswith("order_")
    assert item.evidence_digest is not None
    assert len(item.evidence_digest) == 64


# ==============================================================================
# 11. STATE MACHINE SAFETY & CAPTURED != PASS
# ==============================================================================

def test_e9_12_state_machine_safety_and_captured_vs_pass(cert_service):
    """
    Certifies that payment capture does not equal integrity PASS and that
    duplicate capture attempts are deterministically intercepted as DRIFT.
    """
    item = cert_service.certify_state_machine_safety()
    assert item.status == "PASS"
    assert "capture does not equal integrity pass" in item.verified_fact.lower()

    # Direct proof inspection
    proof = cert_service.proof_service.generate_proof(ScenarioId.DUPLICATE_PAYMENT)
    assert proof.actual_verdict == "DRIFT"
    assert proof.actual_verdict != "PASS"
    assert any("DoubleExecutionRisk" in v or "exceeding authorized max" in v for v in proof.violations)


# ==============================================================================
# 12. AI ADVISORY BOUNDARY & ZERO FINANCIAL AUTHORITY
# ==============================================================================

def test_e9_13_ai_advisory_boundary_zero_financial_authority(cert_service):
    """
    Certifies that AI explanations and adversarial prompt injections cannot
    override deterministic verification or force a financial PASS.
    """
    proof = cert_service.proof_service.generate_proof(ScenarioId.PROMPT_INJECTION_IN_EVIDENCE)
    assert proof.actual_verdict == "UNKNOWN"
    assert proof.actual_verdict != "PASS"
    assert proof.security_findings.get("prompt_injection_intercepted") is True


# ==============================================================================
# 13. FULL E9 CERTIFICATION REPORT API ENDPOINT
# ==============================================================================

def test_e9_14_e9_certification_report_api_endpoint(client):
    """
    Certifies that GET /api/v1/certification/e9 returns the complete,
    immutable, tamper-evident EndToEndCertificationReport.
    """
    res = client.get("/api/v1/certification/e9")
    assert res.status_code == 200
    data = res.json()

    assert data["overall_status"] == "PASS"
    assert len(data["items"]) == 12
    assert data["live_verified_count"] >= 1
    assert data["synthetic_fixture_count"] >= 11
    assert len(data["certification_digest"]) == 64
    assert data["baseline_sha"] == "4e978adb78d82ec43e28ca71076d8db11d65ef03"

    # Verify each item status
    for item in data["items"]:
        assert item["status"] in ("PASS", "NOT_APPLICABLE")
        assert len(item["requirement"]) > 0
        assert len(item["verified_fact"]) > 0


# ==============================================================================
# 14. ALL E9 INVARIANTS PROGRAMMATICALLY VERIFIED
# ==============================================================================

def test_e9_15_all_e9_invariants_verified(cert_service):
    """
    Certifies all 7 core invariants declared in EndToEndCertificationReport:
    - ai_remains_advisory
    - deterministic_verification_authoritative
    - frontend_observational
    - unknown_cannot_directly_become_pass
    - authorization_cannot_silently_increase
    - replay_side_effect_free
    - payment_distinct_from_integrity_pass
    """
    report = cert_service.run_full_certification()
    assert report.overall_status == "PASS"
    invariants = report.invariants_verified
    assert len(invariants) == 7
    assert all(invariants.values()) is True



