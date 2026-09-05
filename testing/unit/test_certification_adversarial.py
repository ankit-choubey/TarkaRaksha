"""
Adversarial and Security boundary tests for Ground-Truth Certification Harness (I12).

Verifies:
1. Ground-truth mutation tampering detection
2. Scenario input snapshot mutation tampering detection (returns INVALID)
3. Actual-result tampering detection
4. Hash tampering detection (input snapshot hash, ground truth hash, actual result hash)
5. Cross-scenario ground truth reuse rejection (INVALID)
6. Cross-transaction certification reuse rejection
7. Expected-vs-actual confusion prevention
8. AI / Network independence (zero LLM calls, zero network access)
9. Authority boundaries (certification cannot authorize, mutate state, override DRIFT, or bypass kill switch)
"""
import pytest
from datetime import datetime, timezone
import hashlib
from unittest.mock import patch

from backend.app.domain.scenario.contracts import (
    ScenarioCategory,
    ScenarioId,
    ScenarioInputSnapshot,
    ScenarioResult,
    ScenarioStatus,
)
from backend.app.domain.scenario.catalog import get_scenario_definition
from backend.app.domain.certification.contracts import (
    CertificationStatus,
    CertificationResult,
    GroundTruthDefinition,
)
from backend.app.domain.certification.ground_truth import (
    CANONICAL_GROUND_TRUTH,
    get_ground_truth,
)
from backend.app.domain.certification.comparator import (
    CertificationComparator,
    compute_actual_result_hash,
)
from backend.app.domain.models import (
    EvidenceAuthority,
    IntegrityStatus,
    TransactionState,
)
from backend.app.services.scenario.definitions import build_scenario_snapshot
from backend.app.services.scenario.runner import ScenarioRunner
from backend.app.services.certification.service import GroundTruthCertificationService


@pytest.fixture
def ref_time() -> datetime:
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


def test_ground_truth_mutation_tampering(ref_time: datetime):
    """
    Mutating expected integrity from PASS to DRIFT changes ground truth digest
    and causes certification to report FAILED when compared against actual PASS execution.
    """
    defn = get_scenario_definition(ScenarioId.HAPPY_PATH)
    snapshot = build_scenario_snapshot(ScenarioId.HAPPY_PATH, reference_time=ref_time)
    actual_res = ScenarioRunner.run(defn, snapshot)

    # Legitimate ground truth
    legit_gt = get_ground_truth(ScenarioId.HAPPY_PATH)
    assert legit_gt.expected_integrity_verdict == "PASS"

    # Mutated ground truth
    tampered_gt = GroundTruthDefinition(
        scenario_id=ScenarioId.HAPPY_PATH,
        ground_truth_id="gt_tampered_happy_path",
        description="Tampered ground truth expecting DRIFT on happy path",
        expected_integrity_verdict="DRIFT",
        expected_security_state=None,
        expected_terminal_state=None,
        expected_mrdp_presence=False,
        expected_abstention=False,
        expected_violation_codes=[],
    )

    # Hashes must differ
    assert tampered_gt.compute_ground_truth_hash() != legit_gt.compute_ground_truth_hash()

    # Comparison against actual PASS result must FAIL
    cert = CertificationComparator.compare(
        ground_truth=tampered_gt,
        actual_result=actual_res,
        snapshot=snapshot,
        certified_at=ref_time,
    )
    assert cert.overall_status == CertificationStatus.FAILED
    assert cert.integrity_match is False
    assert any("IntegrityMismatch" in reason for reason in cert.failure_reasons)


def test_scenario_input_tampering_produces_invalid(ref_time: datetime):
    """
    Modifying the scenario input snapshot after execution so that actual_result.input_snapshot_hash
    differs from snapshot.compute_digest() must produce INVALID, never CERTIFIED or silently FAILED.
    """
    defn = get_scenario_definition(ScenarioId.HAPPY_PATH)
    snapshot = build_scenario_snapshot(ScenarioId.HAPPY_PATH, reference_time=ref_time)
    actual_res = ScenarioRunner.run(defn, snapshot)

    # Tamper with snapshot by altering an intent field that changes compute_digest()
    tampered_intent = snapshot.intent.model_copy(update={"intent_id": "malicious_intent_999"})
    tampered_snapshot = snapshot.model_copy(update={"intent": tampered_intent})

    assert tampered_snapshot.compute_digest() != actual_res.input_snapshot_hash

    gt = get_ground_truth(ScenarioId.HAPPY_PATH)
    cert = CertificationComparator.compare(
        ground_truth=gt,
        actual_result=actual_res,
        snapshot=tampered_snapshot,
        certified_at=ref_time,
    )
    assert cert.overall_status == CertificationStatus.INVALID
    assert any("SnapshotHashMismatchError" in r for r in cert.failure_reasons)


def test_cross_scenario_ground_truth_reuse_rejected(ref_time: datetime):
    """
    Attempting to evaluate scenario B using scenario A's ground truth definition
    must be immediately rejected as INVALID.
    """
    # Run Price Drift
    defn = get_scenario_definition(ScenarioId.PRICE_DRIFT)
    snapshot = build_scenario_snapshot(ScenarioId.PRICE_DRIFT, reference_time=ref_time)
    actual_res = ScenarioRunner.run(defn, snapshot)

    # Attempt to pair with Happy Path ground truth
    happy_gt = get_ground_truth(ScenarioId.HAPPY_PATH)

    cert = CertificationComparator.compare(
        ground_truth=happy_gt,
        actual_result=actual_res,
        snapshot=snapshot,
        certified_at=ref_time,
    )
    assert cert.overall_status == CertificationStatus.INVALID
    assert any("CrossScenarioReuseError" in r for r in cert.failure_reasons)


def test_cross_transaction_reuse_rejected(ref_time: datetime):
    """
    Attempting to certify using a scenario result from a different transaction ID/intent
    causes mismatch with snapshot and is rejected as INVALID.
    """
    defn = get_scenario_definition(ScenarioId.HAPPY_PATH)
    snapshot_a = build_scenario_snapshot(ScenarioId.HAPPY_PATH, reference_time=ref_time)
    actual_res_a = ScenarioRunner.run(defn, snapshot_a)

    # Create distinct snapshot B with different intent id
    tampered_intent = snapshot_a.intent.model_copy(update={"intent_id": "intent_foreign_9999"})
    snapshot_b = snapshot_a.model_copy(update={"intent": tampered_intent})

    gt = get_ground_truth(ScenarioId.HAPPY_PATH)
    cert = CertificationComparator.compare(
        ground_truth=gt,
        actual_result=actual_res_a,
        snapshot=snapshot_b,
        certified_at=ref_time,
    )
    assert cert.overall_status == CertificationStatus.INVALID
    assert any("SnapshotHashMismatchError" in r for r in cert.failure_reasons)


def test_actual_result_hash_tampering_detected(ref_time: datetime):
    """
    Altering the actual result payload changes compute_actual_result_hash,
    ensuring tamper-evidence in downstream verification.
    """
    defn = get_scenario_definition(ScenarioId.PRICE_DRIFT)
    snapshot = build_scenario_snapshot(ScenarioId.PRICE_DRIFT, reference_time=ref_time)
    actual_res = ScenarioRunner.run(defn, snapshot)

    orig_hash = compute_actual_result_hash(actual_res)

    # Tamper with actual result verdict
    tampered_actual = actual_res.model_copy(update={"actual_verdict": IntegrityStatus.PASS})
    tampered_hash = compute_actual_result_hash(tampered_actual)

    assert orig_hash != tampered_hash


def test_expected_vs_actual_confusion_prevention(ref_time: datetime):
    """
    A fabricated ScenarioResult created by copying expected ground truth rather than
    executing through the authoritative pipeline will fail input snapshot integrity verification.
    """
    gt = get_ground_truth(ScenarioId.HAPPY_PATH)
    snapshot = build_scenario_snapshot(ScenarioId.HAPPY_PATH, reference_time=ref_time)

    # Fabricate a fake result with bogus snapshot hash
    fabricated_result = ScenarioResult(
        scenario_id=gt.scenario_id,
        scenario_version="1.0.0",
        scenario_status=ScenarioStatus.PASS,
        expected_verdict=gt.expected_integrity_verdict,
        actual_verdict=str(IntegrityStatus.PASS.value),
        input_snapshot_hash="fake_hash_0000000000000000000000000000000000000000000000000000000000000000",
        reference_time=ref_time,
    )

    cert = CertificationComparator.compare(
        ground_truth=gt,
        actual_result=fabricated_result,
        snapshot=snapshot,
        certified_at=ref_time,
    )
    assert cert.overall_status == CertificationStatus.INVALID
    assert any("SnapshotHashMismatchError" in r for r in cert.failure_reasons)


def test_ai_and_network_independence(ref_time: datetime):
    """
    Ground-Truth Certification must execute completely deterministically without
    any external network calls or LLM / Groq invocations.
    """
    service = GroundTruthCertificationService()

    # Mock any possible network socket or LLM client to ensure zero calls occur
    with patch("socket.socket") as mock_socket:
        suite = service.certify_all(reference_time=ref_time)
        assert suite.is_fully_certified is True
        assert suite.certified_scenarios == 12
        assert mock_socket.call_count == 0


def test_certification_cannot_authorize_or_mutate_transactions(ref_time: datetime):
    """
    Ground-Truth Certification is strictly an audit/verification harness.
    It does NOT possess methods to authorize funds, mutate payment status,
    or bypass the kill switch.
    """
    service = GroundTruthCertificationService()
    # Verify the service contract contains only certification methods
    allowed_methods = {
        "get_ground_truth",
        "list_ground_truths",
        "certify_scenario",
        "certify_all",
        "get_certification_matrix",
    }
    public_methods = {m for m in dir(service) if not m.startswith("_")}
    assert public_methods.issubset(allowed_methods)

    # Verify certification result does not mutate transaction
    res = service.certify_scenario(ScenarioId.PRICE_DRIFT, reference_time=ref_time)
    assert res.overall_status == CertificationStatus.CERTIFIED
    assert res.actual_result["verdict"] == "DRIFT"
    # Ground truth cannot override DRIFT to PASS
    assert res.actual_result["verdict"] != "PASS"

