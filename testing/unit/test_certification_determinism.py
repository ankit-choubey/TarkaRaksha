"""
Determinism, execution order independence, replay compatibility, and capability graph
compatibility tests for Ground-Truth Certification (I12).
"""
import pytest
from datetime import datetime, timezone
import random

from backend.app.domain.scenario.contracts import ScenarioId
from backend.app.domain.certification.contracts import (
    CertificationStatus,
    CertificationResult,
    CertificationSuiteResult,
)
from backend.app.domain.certification.ground_truth import CANONICAL_GROUND_TRUTH
from backend.app.services.certification.service import GroundTruthCertificationService


@pytest.fixture
def cert_service() -> GroundTruthCertificationService:
    return GroundTruthCertificationService()


@pytest.fixture
def ref_time() -> datetime:
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


def test_repeated_certification_digest_stability(
    cert_service: GroundTruthCertificationService,
    ref_time: datetime,
):
    """
    Running the entire 12-scenario certification suite multiple times with the same reference_time
    must yield identical certification results and identical SHA-256 digests.
    """
    runs = 3
    all_suite_results = [cert_service.certify_all(reference_time=ref_time) for _ in range(runs)]

    baseline_suite = all_suite_results[0]
    assert baseline_suite.is_fully_certified is True
    assert baseline_suite.total_scenarios == 12

    for i in range(1, runs):
        suite = all_suite_results[i]
        assert suite.is_fully_certified is True
        assert suite.total_scenarios == baseline_suite.total_scenarios
        assert suite.certified_scenarios == baseline_suite.certified_scenarios

        for base_res, cur_res in zip(baseline_suite.results, suite.results):
            assert base_res.scenario_id == cur_res.scenario_id
            assert base_res.overall_status == cur_res.overall_status
            assert base_res.input_snapshot_hash == cur_res.input_snapshot_hash
            assert base_res.ground_truth_hash == cur_res.ground_truth_hash
            assert base_res.actual_result_hash == cur_res.actual_result_hash
            assert base_res.certification_hash == cur_res.certification_hash


def test_reversed_execution_order_invariance(
    cert_service: GroundTruthCertificationService,
    ref_time: datetime,
):
    """
    Executing scenarios in forward order (01 -> 12) versus reversed order (12 -> 01)
    must produce identical certification results and hashes for each scenario.
    """
    scenarios_forward = list(CANONICAL_GROUND_TRUTH.keys())
    scenarios_reverse = list(reversed(scenarios_forward))

    results_forward = {
        sid: cert_service.certify_scenario(sid, reference_time=ref_time)
        for sid in scenarios_forward
    }

    results_reverse = {
        sid: cert_service.certify_scenario(sid, reference_time=ref_time)
        for sid in scenarios_reverse
    }

    assert len(results_forward) == 12
    assert len(results_reverse) == 12

    for sid in scenarios_forward:
        fwd = results_forward[sid]
        rev = results_reverse[sid]

        assert fwd.overall_status == CertificationStatus.CERTIFIED
        assert rev.overall_status == CertificationStatus.CERTIFIED
        assert fwd.overall_status == rev.overall_status
        assert fwd.certification_hash == rev.certification_hash
        assert fwd.input_snapshot_hash == rev.input_snapshot_hash
        assert fwd.ground_truth_hash == rev.ground_truth_hash
        assert fwd.actual_result_hash == rev.actual_result_hash


def test_shuffled_execution_order_invariance(
    cert_service: GroundTruthCertificationService,
    ref_time: datetime,
):
    """
    Random permutations of scenario execution produce identical certification hashes.
    """
    scenarios = list(CANONICAL_GROUND_TRUTH.keys())
    baseline_hashes = {
        sid: cert_service.certify_scenario(sid, reference_time=ref_time).certification_hash
        for sid in scenarios
    }

    # Deterministic pseudo-random seed for repeatable shuffle test
    rng = random.Random(42)
    shuffled_scenarios = list(scenarios)
    rng.shuffle(shuffled_scenarios)

    shuffled_hashes = {
        sid: cert_service.certify_scenario(sid, reference_time=ref_time).certification_hash
        for sid in shuffled_scenarios
    }

    assert baseline_hashes == shuffled_hashes


def test_replay_compatibility_scenario_08(
    cert_service: GroundTruthCertificationService,
    ref_time: datetime,
):
    """
    Scenario 08 (REPLAY_ATTACK) exercises replay engine / signature verification.
    Certification verifies it correctly detects replay drift, produces MRDP,
    and maintains historical replay integrity without mutation.
    """
    res = cert_service.certify_scenario(ScenarioId.REPLAY_ATTACK, reference_time=ref_time)
    assert res.overall_status == CertificationStatus.CERTIFIED
    assert res.integrity_match is True
    assert res.actual_result["verdict"] == "MISMATCH"


def test_capability_graph_compatibility_scenario_04_and_10(
    cert_service: GroundTruthCertificationService,
    ref_time: datetime,
):
    """
    Scenarios 04 (INVENTORY_DISAPPEARS) and 10 (MERCHANT_AGENT_COMPROMISED)
    exercise I19 merchant capability graph assertions. Certification accurately evaluates
    the capability drift without inventing secondary capability representations.
    """
    # Scenario 04: Inventory Disappears
    res_04 = cert_service.certify_scenario(ScenarioId.INVENTORY_DISAPPEARS, reference_time=ref_time)
    assert res_04.overall_status == CertificationStatus.CERTIFIED
    assert res_04.actual_result["verdict"] == "DRIFT"
    assert any("MissingAuthorizedItem" in v for v in res_04.actual_result["violations"])

    # Scenario 10: Merchant Agent Compromised
    res_10 = cert_service.certify_scenario(ScenarioId.MERCHANT_AGENT_COMPROMISED, reference_time=ref_time)
    assert res_10.overall_status == CertificationStatus.CERTIFIED
    assert res_10.actual_result["verdict"] == "UNKNOWN"
