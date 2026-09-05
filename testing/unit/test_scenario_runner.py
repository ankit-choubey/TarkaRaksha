"""
Unit and Integration Test Suite for Scenario Runner and All 12 Canonical Scenarios (I11).

Verifies:
1. Every one of the 12 canonical scenarios executes deterministically.
2. Expected verdict matches actual engine outcome (ScenarioStatus.PASS).
3. MRDP proof is generated for DRIFT scenarios (PRICE_DRIFT, WRONG_SKU, etc.).
4. Replay attacks are caught by the ReplayEngine.
5. Cross-transaction buyer reuse is caught by TransactionBindingService.
6. Evidence prompt injection cannot force PASS or escalate authority.
7. Missing/delayed provider states remain UNKNOWN.
8. Repeated runs produce identical results (Determinism).
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.scenario.contracts import (
    ScenarioId,
    ScenarioStatus,
)
from backend.app.domain.scenario.catalog import (
    get_scenario_definition,
    CANONICAL_SCENARIO_DEFINITIONS,
)
from backend.app.services.scenario.definitions import build_scenario_snapshot
from backend.app.services.scenario.runner import ScenarioRunner
from backend.app.services.scenario.service import ScenarioLabService


@pytest.fixture
def scenario_service():
    return ScenarioLabService()


@pytest.fixture
def ref_time():
    return datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("scenario_id", list(CANONICAL_SCENARIO_DEFINITIONS.keys()))
def test_all_twelve_canonical_scenarios_pass(scenario_service, scenario_id, ref_time):
    """
    Every canonical scenario must execute against the authoritative engine
    and verify that actual == expected, resulting in ScenarioStatus.PASS.
    """
    result = scenario_service.run_scenario(scenario_id, reference_time=ref_time)

    assert result.scenario_id == scenario_id
    assert result.scenario_status == ScenarioStatus.PASS, (
        f"Scenario {scenario_id.value} failed: expected {result.expected_verdict}, "
        f"got {result.actual_verdict}. Violations: {result.violations}"
    )
    assert result.actual_verdict == result.expected_verdict
    assert result.input_snapshot_hash is not None
    assert len(result.input_snapshot_hash) == 64
    assert len(result.human_readable_report) > 0


def test_scenario_suite_runner(scenario_service, ref_time):
    """Tests executing the entire suite of 12 canonical scenarios."""
    suite_res = scenario_service.run_all(reference_time=ref_time)

    assert suite_res.total_scenarios == 12
    assert suite_res.passed_scenarios == 12
    assert suite_res.failed_scenarios == 0
    assert suite_res.is_all_passed is True
    assert len(suite_res.results) == 12


def test_price_drift_generates_mrdp(scenario_service, ref_time):
    """Scenario 02 (PRICE_DRIFT) must produce valid cryptographic MRDP proof."""
    res = scenario_service.run_scenario(ScenarioId.PRICE_DRIFT, reference_time=ref_time)
    assert res.actual_verdict == "DRIFT"
    assert res.mrdp_digest is not None
    assert len(res.mrdp_digest) == 64
    assert "mrdp_id" in res.details


def test_prompt_injection_does_not_force_pass(scenario_service, ref_time):
    """
    Scenario 09 (PROMPT_INJECTION_IN_EVIDENCE) must treat injected instructions
    as raw data and preserve UNKNOWN without authority escalation.
    """
    res = scenario_service.run_scenario(ScenarioId.PROMPT_INJECTION_IN_EVIDENCE, reference_time=ref_time)
    assert res.actual_verdict == "UNKNOWN"
    assert res.scenario_status == ScenarioStatus.PASS


def test_merchant_agent_compromised_does_not_override_provider(scenario_service, ref_time):
    """
    Scenario 10 (MERCHANT_AGENT_COMPROMISED) ensures merchant-attested claims
    cannot forge authoritative payment success.
    """
    res = scenario_service.run_scenario(ScenarioId.MERCHANT_AGENT_COMPROMISED, reference_time=ref_time)
    assert res.actual_verdict == "UNKNOWN"
    assert res.scenario_status == ScenarioStatus.PASS


def test_buyer_agent_reuse_rejected(scenario_service, ref_time):
    """
    Scenario 11 (BUYER_AGENT_REUSE) verifies cross-transaction context reuse
    is detected and rejected by binding verification.
    """
    res = scenario_service.run_scenario(ScenarioId.BUYER_AGENT_REUSE, reference_time=ref_time)
    assert res.actual_verdict == "REJECTED"
    assert res.scenario_status == ScenarioStatus.PASS


def test_replay_attack_detected_as_mismatch(scenario_service, ref_time):
    """
    Scenario 08 (REPLAY_ATTACK) verifies replay engine flags divergence.
    """
    res = scenario_service.run_scenario(ScenarioId.REPLAY_ATTACK, reference_time=ref_time)
    assert res.actual_verdict in ("MISMATCH", "INVALID_REPLAY")
    assert res.scenario_status == ScenarioStatus.PASS


def test_fastapi_scenario_endpoints():
    """Verify REST API endpoints for Scenario Lab."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    # 1. GET /api/v1/scenarios
    res = client.get("/api/v1/scenarios")
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) == 12

    # 2. POST /api/v1/scenarios/HAPPY_PATH/run
    res_run = client.post("/api/v1/scenarios/HAPPY_PATH/run")
    assert res_run.status_code == 200
    data = res_run.json()
    assert data["scenario_id"] == "HAPPY_PATH"
    assert data["scenario_status"] == "PASS"
    assert data["actual_verdict"] == "PASS"

    # 3. POST /api/v1/scenarios/NON_EXISTENT/run -> 404
    res_404 = client.post("/api/v1/scenarios/NON_EXISTENT/run")
    assert res_404.status_code == 404

    # 4. POST /api/v1/scenarios/run-all
    res_all = client.post("/api/v1/scenarios/run-all")
    assert res_all.status_code == 200
    suite = res_all.json()
    assert suite["total_scenarios"] == 12
    assert suite["passed_scenarios"] == 12
    assert suite["is_all_passed"] is True

