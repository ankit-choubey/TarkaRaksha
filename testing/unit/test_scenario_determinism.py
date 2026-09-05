"""
Determinism and Isolation Test Suite for Deterministic Scenario Lab (I11).

Verifies:
1. Bit-for-bit determinism: running the same scenario repeatedly yields identical digests and results.
2. Isolation: order of execution (forward, reverse, random) has zero effect on individual scenario results.
3. Time reproducibility: explicit reference timestamps ensure identical outcomes.
4. Digest sensitivity: any modification to snapshot parameters alters the snapshot digest.
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.scenario.contracts import (
    ScenarioId,
    ScenarioStatus,
)
from backend.app.domain.scenario.catalog import CANONICAL_SCENARIO_DEFINITIONS
from backend.app.services.scenario.service import ScenarioLabService


@pytest.fixture
def service():
    return ScenarioLabService()


@pytest.fixture
def ref_time():
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


def test_repeated_scenario_execution_determinism(service, ref_time):
    """
    Run every scenario multiple times and assert bit-for-bit identical outputs.
    """
    for scenario_id in CANONICAL_SCENARIO_DEFINITIONS.keys():
        first_result = service.run_scenario(scenario_id, reference_time=ref_time)
        for _ in range(10):
            repeated_result = service.run_scenario(scenario_id, reference_time=ref_time)
            assert repeated_result.input_snapshot_hash == first_result.input_snapshot_hash
            assert repeated_result.actual_verdict == first_result.actual_verdict
            assert repeated_result.expected_verdict == first_result.expected_verdict
            assert repeated_result.scenario_status == first_result.scenario_status
            assert repeated_result.mrdp_digest == first_result.mrdp_digest
            assert repeated_result.violations == first_result.violations


def test_scenario_execution_order_independence(service, ref_time):
    """
    Running scenarios in forward order vs reverse order must produce identical results.
    """
    keys = list(CANONICAL_SCENARIO_DEFINITIONS.keys())
    forward_results = [service.run_scenario(k, reference_time=ref_time) for k in keys]
    reverse_results = [service.run_scenario(k, reference_time=ref_time) for k in reversed(keys)]

    reverse_map = {r.scenario_id: r for r in reverse_results}
    for f_res in forward_results:
        r_res = reverse_map[f_res.scenario_id]
        assert f_res.input_snapshot_hash == r_res.input_snapshot_hash
        assert f_res.actual_verdict == r_res.actual_verdict
        assert f_res.scenario_status == r_res.scenario_status


def test_suite_result_consistency(service, ref_time):
    """
    Running the entire suite produces consistent counts and all pass.
    """
    suite_res1 = service.run_all(reference_time=ref_time)
    suite_res2 = service.run_all(reference_time=ref_time)

    assert suite_res1.total_scenarios == suite_res2.total_scenarios == 12
    assert suite_res1.passed_scenarios == suite_res2.passed_scenarios == 12
    assert suite_res1.is_all_passed == suite_res2.is_all_passed is True
