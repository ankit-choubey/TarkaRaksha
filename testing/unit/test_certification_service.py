"""
Unit tests for GroundTruthCertificationService and API endpoints (I12).
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.domain.scenario.contracts import ScenarioId
from backend.app.domain.certification.contracts import (
    CertificationStatus,
    CertificationResult,
    CertificationSuiteResult,
    CertificationMatrixRow,
)
from backend.app.domain.certification.ground_truth import CANONICAL_GROUND_TRUTH
from backend.app.services.certification.service import GroundTruthCertificationService


@pytest.fixture
def cert_service() -> GroundTruthCertificationService:
    return GroundTruthCertificationService()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_list_ground_truths(cert_service: GroundTruthCertificationService):
    """Test listing all canonical ground truth definitions."""
    gts = cert_service.list_ground_truths()
    assert len(gts) == 12
    scenario_ids = {gt.scenario_id for gt in gts}
    assert ScenarioId.HAPPY_PATH in scenario_ids
    assert ScenarioId.UNKNOWN_PROVIDER_STATE in scenario_ids


def test_certify_single_scenario_happy_path(cert_service: GroundTruthCertificationService):
    """Test single scenario certification for HAPPY_PATH."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    res = cert_service.certify_scenario(ScenarioId.HAPPY_PATH, reference_time=ref_time)

    assert isinstance(res, CertificationResult)
    assert res.scenario_id == "HAPPY_PATH"
    assert res.overall_status == CertificationStatus.CERTIFIED
    assert res.integrity_match is True
    assert res.security_match is True
    assert res.state_match is True
    assert res.mrdp_match is True
    assert res.abstention_match is True
    assert res.violation_match is True
    assert res.authority_match is True
    assert len(res.failure_reasons) == 0
    assert len(res.certification_hash) == 64


def test_certify_all_canonical_scenarios(cert_service: GroundTruthCertificationService):
    """Test that all 12 canonical scenarios are executed through the pipeline and CERTIFIED."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    suite = cert_service.certify_all(reference_time=ref_time)

    assert isinstance(suite, CertificationSuiteResult)
    assert suite.total_scenarios == 12
    assert suite.certified_scenarios == 12
    assert suite.failed_scenarios == 0
    assert suite.invalid_scenarios == 0
    assert suite.is_fully_certified is True
    assert len(suite.results) == 12
    assert len(suite.matrix) == 12

    for row in suite.matrix:
        assert isinstance(row, CertificationMatrixRow)
        assert row.overall_certification == "CERTIFIED"
        assert row.integrity_match is True
        assert row.security_match is True
        assert row.state_match is True


def test_get_certification_matrix(cert_service: GroundTruthCertificationService):
    """Test retrieving typed machine-readable certification matrix rows directly."""
    ref_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
    matrix = cert_service.get_certification_matrix(reference_time=ref_time)

    assert len(matrix) == 12
    for row in matrix:
        assert row.overall_certification == "CERTIFIED"
        assert len(row.certification_hash) == 64


def test_api_list_certifications(client: TestClient):
    """Test GET /api/v1/certifications endpoint."""
    resp = client.get("/api/v1/certifications")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 12
    assert any(d["scenario_id"] == "HAPPY_PATH" for d in data)


def test_api_run_single_certification(client: TestClient):
    """Test POST /api/v1/certifications/{scenario_id}/run endpoint."""
    resp = client.post("/api/v1/certifications/HAPPY_PATH/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_id"] == "HAPPY_PATH"
    assert data["overall_status"] == "CERTIFIED"
    assert data["integrity_match"] is True

    # Unknown scenario
    resp_404 = client.post("/api/v1/certifications/UNKNOWN_SCENARIO_XYZ/run")
    assert resp_404.status_code == 404


def test_api_run_all_certifications(client: TestClient):
    """Test POST /api/v1/certifications/run-all endpoint."""
    resp = client.post("/api/v1/certifications/run-all")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_scenarios"] == 12
    assert data["certified_scenarios"] == 12
    assert data["failed_scenarios"] == 0
    assert data["invalid_scenarios"] == 0
    assert data["is_fully_certified"] is True
    assert len(data["matrix"]) == 12
