"""
Unit tests for Deterministic Certification Comparator (I12).

Verifies:
1. Accurate dimensional comparison yields CERTIFIED when actual matches expected.
2. Cross-scenario mismatch produces INVALID (not FAILED).
3. Snapshot hash mismatch produces INVALID (not FAILED).
4. Outcome divergence produces FAILED.
5. Deterministic certification digest computation.
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.scenario.contracts import ScenarioId
from backend.app.domain.certification.contracts import CertificationStatus
from backend.app.domain.certification.ground_truth import get_ground_truth
from backend.app.domain.certification.comparator import CertificationComparator
from backend.app.services.scenario.definitions import build_scenario_snapshot
from backend.app.services.scenario.runner import ScenarioRunner
from backend.app.domain.scenario.catalog import get_scenario_definition


@pytest.fixture
def ref_time():
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


def test_comparator_happy_path_certified(ref_time):
    """Verify clean HAPPY_PATH execution produces CERTIFIED."""
    gt = get_ground_truth(ScenarioId.HAPPY_PATH)
    snap = build_scenario_snapshot(ScenarioId.HAPPY_PATH, reference_time=ref_time)
    defn = get_scenario_definition(ScenarioId.HAPPY_PATH)
    actual = ScenarioRunner.run(defn, snap)

    cert = CertificationComparator.compare(gt, actual, snap, certified_at=ref_time)
    assert cert.overall_status == CertificationStatus.CERTIFIED
    assert cert.integrity_match is True
    assert cert.mrdp_match is True
    assert cert.abstention_match is True
    assert len(cert.certification_hash) == 64


def test_comparator_price_drift_certified(ref_time):
    """Verify clean PRICE_DRIFT execution produces CERTIFIED with MRDP match."""
    gt = get_ground_truth(ScenarioId.PRICE_DRIFT)
    snap = build_scenario_snapshot(ScenarioId.PRICE_DRIFT, reference_time=ref_time)
    defn = get_scenario_definition(ScenarioId.PRICE_DRIFT)
    actual = ScenarioRunner.run(defn, snap)

    cert = CertificationComparator.compare(gt, actual, snap, certified_at=ref_time)
    assert cert.overall_status == CertificationStatus.CERTIFIED
    assert cert.integrity_match is True
    assert cert.mrdp_match is True
    assert cert.violation_match is True


def test_comparator_cross_scenario_reuse_produces_invalid(ref_time):
    """Attempting to use HAPPY_PATH ground truth against PRICE_DRIFT actual result yields INVALID."""
    gt = get_ground_truth(ScenarioId.HAPPY_PATH)
    price_snap = build_scenario_snapshot(ScenarioId.PRICE_DRIFT, reference_time=ref_time)
    price_defn = get_scenario_definition(ScenarioId.PRICE_DRIFT)
    actual = ScenarioRunner.run(price_defn, price_snap)

    cert = CertificationComparator.compare(gt, actual, price_snap, certified_at=ref_time)
    assert cert.overall_status == CertificationStatus.INVALID
    assert any("CrossScenarioReuseError" in r for r in cert.failure_reasons)


def test_comparator_snapshot_hash_tamper_produces_invalid(ref_time):
    """Tampering with input snapshot hash produces INVALID."""
    gt = get_ground_truth(ScenarioId.HAPPY_PATH)
    snap = build_scenario_snapshot(ScenarioId.HAPPY_PATH, reference_time=ref_time)
    defn = get_scenario_definition(ScenarioId.HAPPY_PATH)
    actual = ScenarioRunner.run(defn, snap)

    tampered_actual = actual.model_copy(update={"input_snapshot_hash": "a" * 64})
    cert = CertificationComparator.compare(gt, tampered_actual, snap, certified_at=ref_time)
    assert cert.overall_status == CertificationStatus.INVALID
    assert any("SnapshotHashMismatchError" in r for r in cert.failure_reasons)


def test_comparator_outcome_divergence_produces_failed(ref_time):
    """When actual verdict differs from ground truth, status is FAILED."""
    gt = get_ground_truth(ScenarioId.PRICE_DRIFT)
    snap = build_scenario_snapshot(ScenarioId.PRICE_DRIFT, reference_time=ref_time)
    defn = get_scenario_definition(ScenarioId.PRICE_DRIFT)
    actual = ScenarioRunner.run(defn, snap)

    # Artificially alter actual verdict to PASS (contrary to ground truth DRIFT)
    divergent_actual = actual.model_copy(update={"actual_verdict": "PASS"})
    cert = CertificationComparator.compare(gt, divergent_actual, snap, certified_at=ref_time)
    assert cert.overall_status == CertificationStatus.FAILED
    assert cert.integrity_match is False
    assert any("IntegrityMismatch" in r for r in cert.failure_reasons)
