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

