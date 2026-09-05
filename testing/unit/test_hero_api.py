"""
API tests for Hero Transaction Control Plane Endpoints (I22).

Tests:
1. POST /api/v1/hero-transaction/run (Hero Recovery Journey B default)
2. POST /api/v1/hero-transaction/run (Happy Path Journey A: simulate_mutation=False)
3. GET /api/v1/hero-transaction/{id} (Retrieve recorded journey)
4. GET /api/v1/hero-transaction/non_existent_id (404 Not Found)
"""
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_run_hero_recovery_journey(client: TestClient):
    """
    POST /api/v1/hero-transaction/run executes the complete hero recovery journey:
    Detect -> Prove -> Repair -> Revalidate -> Execute -> Verify.
    """
    response = client.post(
        "/api/v1/hero-transaction/run",
        json={"simulate_mutation": True},
    )
    assert response.status_code == 200
    data = response.json()

    assert "hero_transaction_id" in data
    assert data["current_stage"] == "COMPLETED"
    assert data["initial_integrity_result"]["status"] == "PASS"
    assert data["mutation"] is not None
    assert data["mutation"]["mutated_price_paise"] == 825000
    assert data["drift_integrity_result"]["status"] == "DRIFT"
    assert data["mrdp"] is not None
    assert data["mrdp"]["error_code"] == "ECONOMIC_AMOUNT_EXCEEDED"
    assert data["drift_notice"] is not None
    assert data["replan_proposal"] is not None
    assert data["remediated_offer"] is not None
    assert data["revalidated_integrity_result"]["status"] == "PASS"
    assert data["binding_outcome"]["is_valid"] is True
    assert data["payment_result"]["status"] == "captured"
    assert data["final_integrity_result"]["status"] == "PASS"
    assert data["tix_chain_valid"] is True
    assert data["tix_message_count"] >= 5
    assert data["replay_result"]["verdict"] == "MATCH"
    assert len(data["lifecycle_digest"]) == 64

    # Verify retrieval
    hero_tx_id = data["hero_transaction_id"]
    get_resp = client.get(f"/api/v1/hero-transaction/{hero_tx_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["hero_transaction_id"] == hero_tx_id
    assert get_data["lifecycle_digest"] == data["lifecycle_digest"]


def test_api_run_hero_happy_path(client: TestClient):
    """
    POST /api/v1/hero-transaction/run with simulate_mutation=False executes clean path.
    """
    response = client.post(
        "/api/v1/hero-transaction/run",
        json={"simulate_mutation": False},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["current_stage"] == "COMPLETED"
    assert data["initial_integrity_result"]["status"] == "PASS"
    assert data["drift_integrity_result"] is None
    assert data["mrdp"] is None
    assert data["final_integrity_result"]["status"] == "PASS"
    assert data["payment_result"]["status"] == "captured"
    assert data["replay_result"]["verdict"] == "MATCH"


def test_api_get_hero_not_found(client: TestClient):
    """
    GET /api/v1/hero-transaction/{id} returns 404 for unknown transaction ID.
    """
    response = client.get("/api/v1/hero-transaction/hero_non_existent_12345")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
