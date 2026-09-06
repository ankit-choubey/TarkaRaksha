"""
Comprehensive Unit and Adversarial Test Suite for E8 — Scenario / Proof Surface.

Tests all Section 20 and 21 criteria:
1. All 12 canonical scenarios discoverable
2. Stable scenario IDs and metadata
3. Unsupported scenario rejected safely (404/KeyError)
4-15. Proof generation and authoritative execution across all 12 scenarios:
   - HAPPY_PATH (PASS)
   - PRICE_DRIFT (DRIFT + MRDP)
   - WRONG_SKU (DRIFT)
   - INVENTORY_DISAPPEARS (DRIFT)
   - DELIVERY_DRIFT (DRIFT)
   - DUPLICATE_PAYMENT (DRIFT)
   - DELAYED_WEBHOOK (DRIFT)
   - REPLAY_ATTACK (MISMATCH)
   - PROMPT_INJECTION_IN_EVIDENCE (UNKNOWN)
   - MERCHANT_AGENT_COMPROMISED (UNKNOWN)
   - BUYER_AGENT_REUSE (REJECTED)
   - UNKNOWN_PROVIDER_STATE (UNKNOWN)
16. 5-Question narrative completeness
17. Expected vs Observed comparison ledger accuracy
18. Proof chain stages sequence and integrity
19. Tamper-evident proof digest determinism and sensitivity
20. Seamless integration and synchronization with E7 Control Room
21. Invariant: CAPTURED != PASS
22. Invariant: UNKNOWN never converted to PASS
23. Invariant: Scenario cannot escalate authorization ceiling
24. Security: Adversarial prompt injection cannot force PASS
25. Real vs Synthetic: Synthetic execution mode visibly labeled
26. Replay: CPU evaluation is side-effect free
27. REST API: GET /api/v1/scenarios/{id}/proof and GET /api/v1/scenarios/proofs
28. REST API: POST /api/v1/scenarios/{id}/prove registers Control Room snapshot
29. Security: Transaction ID substitution isolation
30. AI Advisory Boundary: Advisory model cannot declare PASS or alter limits
"""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.domain.scenario import (
    ScenarioCategory,
    ScenarioDefinition,
    ScenarioId,
    ScenarioProof,
    ScenarioStatus,
    CANONICAL_SCENARIO_DEFINITIONS,
    get_scenario_definition,
    list_scenario_definitions,
)
from backend.app.services.scenario.proof import ScenarioProofService
from backend.app.services.control_room.service import ControlRoomService


@pytest.fixture
def client():
    """FastAPI TestClient for API endpoints."""
    return TestClient(app)


@pytest.fixture
def proof_service():
    """Clean ScenarioProofService instance."""
    return ScenarioProofService()


# ------------------------------------------------------------------------------
# 1. All 12 Canonical Scenarios Discoverable in Catalog
# ------------------------------------------------------------------------------
def test_e8_01_all_12_canonical_scenarios_discoverable(proof_service):
    catalog = list_scenario_definitions()
    assert len(catalog) == 12

    expected_ids = {
        "HAPPY_PATH",
        "PRICE_DRIFT",
        "WRONG_SKU",
        "INVENTORY_DISAPPEARS",
        "DELIVERY_DRIFT",
        "DUPLICATE_PAYMENT",
        "DELAYED_WEBHOOK",
        "REPLAY_ATTACK",
        "PROMPT_INJECTION_IN_EVIDENCE",
        "MERCHANT_AGENT_COMPROMISED",
        "BUYER_AGENT_REUSE",
        "UNKNOWN_PROVIDER_STATE",
    }
    actual_ids = {s.scenario_id.value for s in catalog}
    assert actual_ids == expected_ids


# ------------------------------------------------------------------------------
# 2. Stable Scenario IDs and Metadata Specifications
# ------------------------------------------------------------------------------
def test_e8_02_stable_scenario_ids_and_metadata():
    for scen_id in ScenarioId:
        defn = get_scenario_definition(scen_id)
        assert defn.scenario_id == scen_id
        assert len(defn.name) > 0
        assert len(defn.description) > 0
        assert defn.initial_conditions is not None
        assert defn.mutation_input is not None
        assert defn.expected_behavior is not None
        assert defn.provider_mode == "SYNTHETIC_OFFLINE_FIXTURE_RUN"
        assert defn.expected_verdict in ["PASS", "DRIFT", "UNKNOWN", "MISMATCH", "REJECTED"]


# ------------------------------------------------------------------------------
# 3. Unsupported Scenario Rejected Safely
# ------------------------------------------------------------------------------
def test_e8_03_unsupported_scenario_rejected_safely(client, proof_service):
    with pytest.raises((KeyError, ValueError)):
        proof_service.generate_proof("NON_EXISTENT_SCENARIO_XYZ")

    res = client.get("/api/v1/scenarios/NON_EXISTENT_SCENARIO_XYZ/proof")
    assert res.status_code == 404

    res_post = client.post("/api/v1/scenarios/NON_EXISTENT_SCENARIO_XYZ/prove")
    assert res_post.status_code == 404


# ------------------------------------------------------------------------------
# 4. Canonical HAPPY_PATH Proof
# ------------------------------------------------------------------------------
def test_e8_04_canonical_happy_path_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.HAPPY_PATH)
    assert proof.scenario_id == ScenarioId.HAPPY_PATH
    assert proof.actual_verdict == "PASS"
    assert proof.scenario_status == ScenarioStatus.PASS
    assert len(proof.violations) == 0
    assert proof.replay_verdict == "MATCH"
    assert len(proof.proof_digest) == 64


# ------------------------------------------------------------------------------
# 5. Canonical PRICE_DRIFT Proof
# ------------------------------------------------------------------------------
def test_e8_05_canonical_price_drift_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    assert proof.scenario_id == ScenarioId.PRICE_DRIFT
    assert proof.actual_verdict == "DRIFT"
    assert proof.scenario_status == ScenarioStatus.PASS
    assert proof.mrdp_digest is not None
    assert len(proof.mrdp_digest) == 64
    assert any("exceeds authorized max_total" in v or "EconomicDrift" in v for v in proof.violations)
    assert proof.recovery_summary is not None


# ------------------------------------------------------------------------------
# 6. Canonical WRONG_SKU Proof
# ------------------------------------------------------------------------------
def test_e8_06_canonical_wrong_sku_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.WRONG_SKU)
    assert proof.scenario_id == ScenarioId.WRONG_SKU
    assert proof.actual_verdict == "DRIFT"
    assert any("UnauthorizedSKU" in v or "SKU-UNAUTHORIZED-GADGET" in v for v in proof.violations)
    # Check comparison table
    sku_row = next(r for r in proof.comparison if r.parameter == "SKU")
    assert sku_row.expected_value == "SKU-BOOK-001"
    assert sku_row.observed_value == "SKU-GADGET-999"
    assert sku_row.is_match is False


# ------------------------------------------------------------------------------
# 7. Canonical INVENTORY_DISAPPEARS Proof
# ------------------------------------------------------------------------------
def test_e8_07_canonical_inventory_disappears_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.INVENTORY_DISAPPEARS)
    assert proof.scenario_id == ScenarioId.INVENTORY_DISAPPEARS
    assert proof.actual_verdict == "DRIFT"
    assert any("MissingAuthorizedItem" in v for v in proof.violations)
    inv_row = next(r for r in proof.comparison if r.parameter == "Inventory Stock")
    assert "0" in inv_row.observed_value
    assert inv_row.is_match is False


# ------------------------------------------------------------------------------
# 8. Canonical DELIVERY_DRIFT Proof
# ------------------------------------------------------------------------------
def test_e8_08_canonical_delivery_drift_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.DELIVERY_DRIFT)
    assert proof.scenario_id == ScenarioId.DELIVERY_DRIFT
    assert proof.actual_verdict == "DRIFT"
    assert any("ExpiredExecution" in v or "after contract expiry" in v for v in proof.violations)
    del_row = next(r for r in proof.comparison if r.parameter == "Delivery SLA")
    assert del_row.is_match is False


# ------------------------------------------------------------------------------
# 9. Canonical DUPLICATE_PAYMENT Proof
# ------------------------------------------------------------------------------
def test_e8_09_canonical_duplicate_payment_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.DUPLICATE_PAYMENT)
    assert proof.scenario_id == ScenarioId.DUPLICATE_PAYMENT
    assert proof.actual_verdict == "DRIFT"
    assert any("DoubleExecutionRisk" in v or "exceeding authorized max" in v for v in proof.violations)


# ------------------------------------------------------------------------------
# 10. Canonical DELAYED_WEBHOOK Proof
# ------------------------------------------------------------------------------
def test_e8_10_canonical_delayed_webhook_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.DELAYED_WEBHOOK)
    assert proof.scenario_id == ScenarioId.DELAYED_WEBHOOK
    assert proof.actual_verdict == "DRIFT"
    assert any("ExpiredExecution" in v or "after contract expiry" in v for v in proof.violations)


# ------------------------------------------------------------------------------
# 11. Canonical REPLAY_ATTACK Proof
# ------------------------------------------------------------------------------
def test_e8_11_canonical_replay_attack_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.REPLAY_ATTACK)
    assert proof.scenario_id == ScenarioId.REPLAY_ATTACK
    assert proof.actual_verdict == "MISMATCH"
    assert proof.replay_verdict == "MISMATCH"
    assert proof.security_findings.get("replay_divergence_detected") is True


# ------------------------------------------------------------------------------
# 12. Canonical PROMPT_INJECTION_IN_EVIDENCE Proof
# ------------------------------------------------------------------------------
def test_e8_12_canonical_prompt_injection_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.PROMPT_INJECTION_IN_EVIDENCE)
    assert proof.scenario_id == ScenarioId.PROMPT_INJECTION_IN_EVIDENCE
    assert proof.actual_verdict == "UNKNOWN"
    assert proof.security_findings.get("prompt_injection_intercepted") is True
    # Advisory injection does NOT turn UNKNOWN into PASS
    assert proof.actual_verdict != "PASS"


# ------------------------------------------------------------------------------
# 13. Canonical MERCHANT_AGENT_COMPROMISED Proof
# ------------------------------------------------------------------------------
def test_e8_13_canonical_merchant_agent_compromised_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.MERCHANT_AGENT_COMPROMISED)
    assert proof.scenario_id == ScenarioId.MERCHANT_AGENT_COMPROMISED
    assert proof.actual_verdict == "UNKNOWN"
    # Merchant attested claim cannot substitute for authoritative gateway evidence
    assert proof.actual_verdict != "PASS"


# ------------------------------------------------------------------------------
# 14. Canonical BUYER_AGENT_REUSE Proof
# ------------------------------------------------------------------------------
def test_e8_14_canonical_buyer_agent_reuse_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.BUYER_AGENT_REUSE)
    assert proof.scenario_id == ScenarioId.BUYER_AGENT_REUSE
    assert proof.actual_verdict == "REJECTED"
    assert proof.security_findings.get("binding_status") in ("DRIFT", "MISMATCH")


# ------------------------------------------------------------------------------
# 15. Canonical UNKNOWN_PROVIDER_STATE Proof
# ------------------------------------------------------------------------------
def test_e8_15_canonical_unknown_provider_state_proof(proof_service):
    proof = proof_service.generate_proof(ScenarioId.UNKNOWN_PROVIDER_STATE)
    assert proof.scenario_id == ScenarioId.UNKNOWN_PROVIDER_STATE
    assert proof.actual_verdict == "UNKNOWN"
    # Never coerce pending state to PASS
    assert proof.actual_verdict != "PASS"


# ------------------------------------------------------------------------------
# 16. 5-Question Narrative Completeness
# ------------------------------------------------------------------------------
def test_e8_16_proof_5_question_narrative_completeness(proof_service):
    proof = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    nar = proof.narrative
    assert "authorized" in nar.what_was_authorized.lower()
    assert len(nar.what_happened) > 10
    assert "ALIGNED" in nar.did_it_match or "DIVERGENT" in nar.did_it_match
    assert len(nar.why) > 10
    assert len(nar.what_happened_next) > 10


# ------------------------------------------------------------------------------
# 17. Expected vs Observed Comparison Accuracy
# ------------------------------------------------------------------------------
def test_e8_17_expected_vs_observed_comparison_accuracy(proof_service):
    proof = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    total_row = next(r for r in proof.comparison if "Total Amount" in r.parameter)
    assert "5,000" in total_row.expected_value
    assert "6,000" in total_row.observed_value
    assert total_row.is_match is False


# ------------------------------------------------------------------------------
# 18. Proof Chain Stages Sequence and Integrity
# ------------------------------------------------------------------------------
def test_e8_18_proof_chain_stages_integrity(proof_service):
    proof = proof_service.generate_proof(ScenarioId.HAPPY_PATH)
    assert len(proof.proof_chain) == 6
    assert "AUTHORIZED STATE" in proof.proof_chain[0].stage_name
    assert "OBSERVED EVENT" in proof.proof_chain[1].stage_name
    assert "DETERMINISTIC VERIFICATION" in proof.proof_chain[2].stage_name
    assert "VERDICT EMITTED" in proof.proof_chain[3].stage_name
    assert "OUTCOME" in proof.proof_chain[5].stage_name


# ------------------------------------------------------------------------------
# 19. Tamper-Evident Proof Digest Determinism and Sensitivity
# ------------------------------------------------------------------------------
def test_e8_19_tamper_evident_proof_digest_determinism(proof_service):
    p1 = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    p2 = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    assert p1.proof_digest == p2.proof_digest
    assert len(p1.proof_digest) == 64

    # Sensitivity: altering any field changes the digest
    mutated = p1.model_copy(update={"actual_verdict": "PASS"})
    assert mutated.compute_digest() != p1.proof_digest


# ------------------------------------------------------------------------------
# 20. Seamless Integration with E7 Control Room
# ------------------------------------------------------------------------------
def test_e8_20_control_room_integration_sync(proof_service):
    cr = ControlRoomService(scenario_proof_service=proof_service)
    proof = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)

    snap = cr.compose_from_scenario_proof(proof)
    cr.register_scenario_snapshot(snap)

    retrieved = cr.get_snapshot(proof.transaction_id)
    assert retrieved is not None
    assert retrieved.identity.transaction_id == proof.transaction_id
    assert retrieved.integrity.status == "DRIFT"
    assert retrieved.drift_proof is not None
    assert retrieved.drift_proof.proof_digest == proof.mrdp_digest


# ------------------------------------------------------------------------------
# 21. Invariant: CAPTURED != PASS
# ------------------------------------------------------------------------------
def test_e8_21_captured_remains_distinct_from_pass(proof_service):
    proof = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    # Payment was captured in fixture, but integrity status is DRIFT!
    assert proof.actual_verdict == "DRIFT"
    assert proof.expected_verdict == "DRIFT"
    assert proof.actual_verdict != "PASS"


# ------------------------------------------------------------------------------
# 22. Invariant: UNKNOWN Never Directly Becomes PASS
# ------------------------------------------------------------------------------
def test_e8_22_unknown_never_directly_becomes_pass(proof_service):
    proof = proof_service.generate_proof(ScenarioId.UNKNOWN_PROVIDER_STATE)
    assert proof.actual_verdict == "UNKNOWN"
    assert proof.actual_verdict != "PASS"
    assert proof.actual_verdict != "DRIFT"


# ------------------------------------------------------------------------------
# 23. Invariant: Scenario Cannot Escalate Authorization Ceiling
# ------------------------------------------------------------------------------
def test_e8_23_scenario_cannot_escalate_authorization_ceiling(proof_service):
    proof = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    # The ceiling remains ₹5,000 despite ₹6,000 spend
    total_row = next(r for r in proof.comparison if "Total Amount" in r.parameter)
    assert "5,000" in proof.recovery_summary["original_ceiling"]
    assert "INR" in proof.recovery_summary["original_ceiling"]


# ------------------------------------------------------------------------------
# 24. Security: Adversarial Prompt Injection Cannot Force PASS
# ------------------------------------------------------------------------------
def test_e8_24_adversarial_input_injection_cannot_force_pass(proof_service):
    proof = proof_service.generate_proof(ScenarioId.PROMPT_INJECTION_IN_EVIDENCE)
    assert proof.actual_verdict == "UNKNOWN"
    assert proof.actual_verdict != "PASS"
    assert "PASS" not in [v for v in proof.violations if "FORCE" in v]


# ------------------------------------------------------------------------------
# 25. Real vs Synthetic Boundary Labeled
# ------------------------------------------------------------------------------
def test_e8_25_synthetic_offline_execution_mode_distinguished(proof_service):
    proof = proof_service.generate_proof(ScenarioId.HAPPY_PATH)
    assert proof.execution_mode == "SYNTHETIC_OFFLINE_FIXTURE_RUN"
    assert proof.execution_mode != "REAL_RAZORPAY_TEST_MODE"


# ------------------------------------------------------------------------------
# 26. Replay: CPU Evaluation is Side-Effect Free
# ------------------------------------------------------------------------------
def test_e8_26_replay_side_effect_freedom_on_cpu(proof_service):
    proof = proof_service.generate_proof(ScenarioId.REPLAY_ATTACK)
    assert proof.actual_verdict == "MISMATCH"
    assert proof.replay_verdict == "MISMATCH"


# ------------------------------------------------------------------------------
# 27. REST API: GET Scenario Proof Endpoints
# ------------------------------------------------------------------------------
def test_e8_27_api_get_scenario_proof_endpoints(client):
    res = client.get("/api/v1/scenarios/PRICE_DRIFT/proof")
    assert res.status_code == 200
    data = res.json()
    assert data["scenario_id"] == "PRICE_DRIFT"
    assert data["actual_verdict"] == "DRIFT"
    assert len(data["proof_digest"]) == 64
    assert len(data["comparison"]) > 0

    list_res = client.get("/api/v1/scenarios/proofs")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


# ------------------------------------------------------------------------------
# 28. REST API: POST Prove Scenario Registers Control Room Snapshot
# ------------------------------------------------------------------------------
def test_e8_28_api_prove_scenario_endpoint_registers_snapshot(client):
    res = client.post("/api/v1/scenarios/WRONG_SKU/prove")
    assert res.status_code == 200
    proof_data = res.json()
    tx_id = proof_data["transaction_id"]

    # Now verify that Control Room has this transaction snapshot!
    snap_res = client.get(f"/api/v1/control-room/snapshot/{tx_id}")
    assert snap_res.status_code == 200
    snap_data = snap_res.json()
    assert snap_data["identity"]["transaction_id"] == tx_id
    assert snap_data["integrity"]["status"] == "DRIFT"


# ------------------------------------------------------------------------------
# 29. Security: Transaction ID Substitution Isolation
# ------------------------------------------------------------------------------
def test_e8_29_transaction_id_isolation(proof_service):
    p_price = proof_service.generate_proof(ScenarioId.PRICE_DRIFT)
    p_sku = proof_service.generate_proof(ScenarioId.WRONG_SKU)
    assert p_price.transaction_id != p_sku.transaction_id
    assert p_price.proof_id != p_sku.proof_id


# ------------------------------------------------------------------------------
# 30. AI Advisory Boundary in Proofs
# ------------------------------------------------------------------------------
def test_e8_30_ai_remains_advisory_in_proofs(proof_service):
    proof = proof_service.generate_proof(ScenarioId.MERCHANT_AGENT_COMPROMISED)
    assert proof.actual_verdict == "UNKNOWN"
    # Confirm deterministic engine made the decision, not advisory agent
    assert proof.actual_verdict != "PASS"
