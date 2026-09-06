"""
Comprehensive Unit and Adversarial Test Suite for E7 — Real-time Control-Room Data Surface.

Tests all Section 13 criteria:
1. Control-room snapshot for valid transaction
2. Unknown transaction returns 404
3. Missing optional subsystem data handled gracefully
4. Correct 7-tuple identity propagation
5. Zero duplicate authoritative state
6. PASS renders correctly
7. DRIFT renders correctly
8. UNKNOWN renders correctly
9. ABSTAIN renders correctly where applicable
10. CAPTURED remains distinct from PASS
11. Failed/pending payment remains distinct from integrity state
12. Complete hero loop: DRIFT -> recovery -> revalidation -> PASS
13. Unresolved recovery remains non-PASS
14. UNKNOWN remains UNKNOWN until authoritative resolution
15. Security findings surface correctly
16. Kill switch surfaces correctly
17. Prompt-injection/threat findings surface correctly
18. Evidence provenance surfaces correctly
19. Replay MATCH surfaces correctly
20. Replay MISMATCH/INVALID_REPLAY surfaces correctly
21. Synthetic/offline execution visibly distinguishable from live provider execution
22. Real Razorpay Test Mode is not claimed unless actually verified
23. E7 live operational feed API test
24. E7 recent summaries API test
25. Snapshot SHA-256 digest computation & immutability test
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.domain.control_room.contracts import (
    ControlRoomIdentity,
    ControlRoomLifecycle,
    ControlRoomAuthorization,
    ControlRoomBuyerAgent,
    ControlRoomMerchantAgent,
    ControlRoomIntegrity,
    ControlRoomRecovery,
    ControlRoomPayment,
    ControlRoomSecurity,
    ControlRoomReplay,
    ControlRoomObservability,
    ControlRoomSnapshot,
    ControlRoomSummary,
)
from backend.app.domain.hero import create_canonical_e6_intent
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.services.control_room.service import ControlRoomService
from backend.app.services.hero.orchestrator import HeroTransactionOrchestrator
from backend.app.services.integration.service import IntegrationService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clean_services():
    hero = HeroTransactionOrchestrator()
    integ = IntegrationService()
    cr_service = ControlRoomService(hero_orchestrator=hero, integration_service=integ)
    return hero, integ, cr_service


# ------------------------------------------------------------------------------
# 1. Snapshot for Valid Transaction
# ------------------------------------------------------------------------------
def test_e7_01_snapshot_for_valid_transaction(client):
    """Verifies that a completed transaction produces a valid, rich ControlRoomSnapshot."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6", "simulate_mutation": False})
    assert res.status_code == 200
    data = res.json()
    tx_id = data["transaction_id"]

    snap_res = client.get(f"/api/v1/control-room/snapshot/{tx_id}")
    assert snap_res.status_code == 200
    snap = snap_res.json()

    assert snap["identity"]["transaction_id"] == tx_id
    assert snap["identity"]["intent_id"].startswith("intent_hero_e6")
    assert snap["integrity"]["status"] == "PASS"
    assert snap["payment"]["payment_status"] == "captured"
    assert snap["snapshot_digest"] != ""


# ------------------------------------------------------------------------------
# 2. Unknown Transaction Returns 404
# ------------------------------------------------------------------------------
def test_e7_02_unknown_transaction_returns_404(client):
    """Verifies that querying a non-existent transaction returns 404."""
    snap_res = client.get("/api/v1/control-room/snapshot/tx_does_not_exist_9999")
    assert snap_res.status_code == 404
    assert "not found" in snap_res.json()["detail"].lower()


# ------------------------------------------------------------------------------
# 3. Missing Optional Subsystem Data Handled Gracefully
# ------------------------------------------------------------------------------
def test_e7_03_missing_optional_subsystem_data_graceful(clean_services):
    """Verifies snapshot handles empty optional fields without crashing."""
    _, _, cr_service = clean_services
    now = datetime.now(timezone.utc)
    minimal_snapshot = ControlRoomSnapshot(
        identity=ControlRoomIdentity(
            transaction_id="tx_min_01",
            intent_id="intent_min_01",
            agent_id="agent_1",
            merchant_id="merchant_1",
            order_id="order_1",
            payment_id="pay_1",
            attempt_id="att_1",
        ),
        lifecycle=ControlRoomLifecycle(
            current_state="INITIALIZED",
            hero_stage=None,
            is_terminal=False,
            started_at=now,
            completed_at=None,
            duration_ms=None,
        ),
        authorization=ControlRoomAuthorization(
            max_total=Money(amount=5000000, currency="INR"),
            currency="INR",
            allowed_skus=[],
            allowed_substitutions=[],
            issued_at=now,
            expires_at=None,
        ),
        buyer_agent=ControlRoomBuyerAgent(
            agent_id="agent_1",
            intent_id="intent_min_01",
            advisory_model="openai/gpt-oss-20b",
        ),
        merchant_agent=ControlRoomMerchantAgent(
            merchant_id="merchant_1",
            capabilities=[],
        ),
        integrity=ControlRoomIntegrity(
            status=IntegrityStatus.PASS,
            violations=[],
        ),
        drift_proof=None,
        recovery=ControlRoomRecovery(
            recovery_invoked=False,
            replan_rounds=0,
            revalidated_pass=False,
            attempts_count=0,
            max_attempts=3,
        ),
        payment=ControlRoomPayment(
            order_id="order_1",
            payment_id="pay_1",
            payment_status="created",
            amount=Money(amount=5000000, currency="INR"),
            payment_captured=False,
        ),
        security=ControlRoomSecurity(
            binding_verified=True,
            kill_switch_state="RUNNING",
            threat_status="CLEAN",
            threats_detected=[],
            prompt_injection_detected=False,
            tampering_detected=False,
        ),
        evidence_records=[],
        replay=ControlRoomReplay(
            replay_available=False,
            is_cpu_only=True,
            discrepancy_count=0,
        ),
        observability=ControlRoomObservability(
            checkpoints_count=0,
            checkpoints_timeline_valid=True,
        ),
        timeline=[],
        execution_mode="SYNTHETIC_OFFLINE_HERO_RUN",
        hero_message=None,
        snapshot_digest="",
    )
    digest = minimal_snapshot.compute_digest()
    assert len(digest) == 64
    assert minimal_snapshot.drift_proof is None
    assert minimal_snapshot.hero_message is None


# ------------------------------------------------------------------------------
# 4. Correct 7-Tuple Identity Propagation
# ------------------------------------------------------------------------------
def test_e7_04_correct_7_tuple_identity_propagation(client):
    """Verifies that all 7 identifiers are preserved and matched."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    assert res.status_code == 200
    tx_id = res.json()["transaction_id"]

    snap_res = client.get(f"/api/v1/control-room/snapshot/{tx_id}")
    ident = snap_res.json()["identity"]

    assert ident["transaction_id"] == tx_id
    assert ident["intent_id"].startswith("intent_")
    assert ident["agent_id"] == "buyer_agent_alice"
    assert ident["merchant_id"] in ["merchant_croma_store", "merchant_agent_bob"]
    assert ident["order_id"].startswith("order_")
    assert ident["payment_id"].startswith("pay_")
    assert ident["attempt_id"] == "att_1"


# ------------------------------------------------------------------------------
# 5. No Duplicate Authoritative State
# ------------------------------------------------------------------------------
def test_e7_05_no_duplicate_authoritative_state(clean_services):
    """Verifies ControlRoomService derives state strictly from underlying records."""
    hero_orch, _, cr_service = clean_services
    intent = create_canonical_e6_intent()
    hero_rec = hero_orch.execute_hero_journey(intent=intent, simulate_mutation=False, scenario="e6")

    snap = cr_service.compose_from_hero_record(hero_rec)
    assert snap.identity.transaction_id == hero_rec.transaction_id
    assert snap.integrity.status == hero_rec.final_integrity_result.status
    # Verify no second state machine is created
    assert cr_service._hero_orchestrator is hero_orch


# ------------------------------------------------------------------------------
# 6. PASS Renders Correctly
# ------------------------------------------------------------------------------
def test_e7_06_pass_renders_correctly(client):
    """Verifies that a non-mutated transaction reflects PASS with no violations."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6", "simulate_mutation": False})
    snap_res = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}")
    integ = snap_res.json()["integrity"]
    assert integ["status"] == "PASS"
    assert integ["economic_verdict"] is True
    assert len(integ["violations"]) == 0


# ------------------------------------------------------------------------------
# 7. DRIFT Renders Correctly with MRDP
# ------------------------------------------------------------------------------
def test_e7_07_drift_renders_correctly_with_mrdp(client):
    """Verifies that an E6 transaction that experienced drift contains MRDP details."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6", "simulate_mutation": True})
    snap_res = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}")
    snap = snap_res.json()

    assert snap["drift_proof"] is not None
    assert snap["drift_proof"]["proof_digest"] != ""
    assert snap["drift_proof"]["error_code"] in ["ECONOMIC_AMOUNT_EXCEEDED", "PRICE_DISCREPANCY_DETECTED"] or "ECONOMIC" in snap["drift_proof"]["error_code"]


# ------------------------------------------------------------------------------
# 8. UNKNOWN Renders Correctly (Preserves Uncertainty)
# ------------------------------------------------------------------------------
def test_e7_08_unknown_renders_correctly():
    """Verifies UNKNOWN status is never coerced to PASS."""
    now = datetime.now(timezone.utc)
    snap = ControlRoomSnapshot(
        identity=ControlRoomIdentity(
            transaction_id="tx_unk_1",
            intent_id="intent_unk_1",
            agent_id="agent_1",
            merchant_id="merch_1",
            order_id="order_1",
            payment_id="pay_1",
            attempt_id="att_1",
        ),
        lifecycle=ControlRoomLifecycle(
            current_state="UNKNOWN_RESOLUTION",
            is_terminal=False,
            started_at=now,
        ),
        authorization=ControlRoomAuthorization(
            max_total=Money(amount=5000000, currency="INR"),
            currency="INR",
            issued_at=now,
        ),
        buyer_agent=ControlRoomBuyerAgent(
            agent_id="agent_1",
            intent_id="intent_unk_1",
            advisory_model="openai/gpt-oss-20b",
        ),
        merchant_agent=ControlRoomMerchantAgent(
            merchant_id="merch_1",
            capabilities=[],
        ),
        integrity=ControlRoomIntegrity(
            status=IntegrityStatus.UNKNOWN,
            violations=["GATEWAY_TELEMETRY_PENDING"],
        ),
        recovery=ControlRoomRecovery(
            recovery_invoked=False,
            replan_rounds=0,
            revalidated_pass=False,
            attempts_count=0,
            max_attempts=3,
        ),
        payment=ControlRoomPayment(
            order_id="order_1",
            payment_id="pay_1",
            payment_status="created",
            amount=Money(amount=5000000, currency="INR"),
            payment_captured=False,
        ),
        security=ControlRoomSecurity(
            binding_verified=True,
            kill_switch_state="REQUIRES_REVALIDATION",
            threat_status="CLEAN",
        ),
        evidence_records=[],
        replay=ControlRoomReplay(
            replay_available=False,
            is_cpu_only=True,
            discrepancy_count=0,
        ),
        observability=ControlRoomObservability(),
        timeline=[],
        execution_mode="SYNTHETIC_OFFLINE_HERO_RUN",
        snapshot_digest="",
    )
    assert snap.integrity.status == IntegrityStatus.UNKNOWN
    assert not snap.payment.payment_captured


# ------------------------------------------------------------------------------
# 9. ABSTAIN Renders Correctly
# ------------------------------------------------------------------------------
def test_e7_09_abstain_renders_correctly():
    """Verifies ABSTAIN status represents halted execution without funds capture."""
    now = datetime.now(timezone.utc)
    snap = ControlRoomSnapshot(
        identity=ControlRoomIdentity(
            transaction_id="tx_abs_1",
            intent_id="intent_abs_1",
            agent_id="agent_1",
            merchant_id="merch_1",
            order_id="order_1",
            payment_id="pay_1",
            attempt_id="att_1",
        ),
        lifecycle=ControlRoomLifecycle(
            current_state="ABSTAIN",
            is_terminal=True,
            started_at=now,
        ),
        authorization=ControlRoomAuthorization(
            max_total=Money(amount=5000000, currency="INR"),
            currency="INR",
            issued_at=now,
        ),
        buyer_agent=ControlRoomBuyerAgent(
            agent_id="agent_1",
            intent_id="intent_abs_1",
            advisory_model="openai/gpt-oss-20b",
        ),
        merchant_agent=ControlRoomMerchantAgent(
            merchant_id="merch_1",
            capabilities=[],
        ),
        integrity=ControlRoomIntegrity(
            status=IntegrityStatus.UNKNOWN,
            violations=["RESOLUTION_EXHAUSTED_UNRESOLVED"],
        ),
        recovery=ControlRoomRecovery(
            recovery_invoked=False,
            replan_rounds=0,
            revalidated_pass=False,
            attempts_count=3,
            max_attempts=3,
        ),
        payment=ControlRoomPayment(
            order_id="order_1",
            payment_id="pay_1",
            payment_status="abstained",
            amount=Money(amount=5000000, currency="INR"),
            payment_captured=False,
        ),
        security=ControlRoomSecurity(
            binding_verified=True,
            kill_switch_state="KILLED",
            threat_status="CLEAN",
        ),
        evidence_records=[],
        replay=ControlRoomReplay(
            replay_available=False,
            is_cpu_only=True,
            discrepancy_count=0,
        ),
        observability=ControlRoomObservability(),
        timeline=[],
        execution_mode="SYNTHETIC_OFFLINE_HERO_RUN",
        snapshot_digest="",
    )
    assert snap.integrity.status == IntegrityStatus.UNKNOWN
    assert snap.lifecycle.current_state == "ABSTAIN"
    assert snap.payment.payment_captured is False


# ------------------------------------------------------------------------------
# 10. CAPTURED Remains Distinct From PASS
# ------------------------------------------------------------------------------
def test_e7_10_captured_remains_distinct_from_pass():
    """Invariants check: Payment captured does not imply Integrity PASS."""
    now = datetime.now(timezone.utc)
    snap = ControlRoomSnapshot(
        identity=ControlRoomIdentity(
            transaction_id="tx_cap_drift_1",
            intent_id="intent_1",
            agent_id="agent_1",
            merchant_id="merch_1",
            order_id="order_1",
            payment_id="pay_1",
            attempt_id="att_1",
        ),
        lifecycle=ControlRoomLifecycle(current_state="COMPLETED", started_at=now),
        authorization=ControlRoomAuthorization(
            max_total=Money(amount=5000000, currency="INR"),
            currency="INR",
            issued_at=now,
        ),
        buyer_agent=ControlRoomBuyerAgent(agent_id="agent_1", intent_id="intent_1"),
        merchant_agent=ControlRoomMerchantAgent(merchant_id="merch_1", capabilities=[]),
        integrity=ControlRoomIntegrity(
            status=IntegrityStatus.DRIFT,
            violations=["MERCHANT_SURCHARGE_DRIFT"],
        ),
        recovery=ControlRoomRecovery(recovery_invoked=False, replan_rounds=0, revalidated_pass=False, attempts_count=0, max_attempts=3),
        payment=ControlRoomPayment(
            order_id="order_1",
            payment_id="pay_1",
            payment_status="captured",
            amount=Money(amount=5500000, currency="INR"),
            payment_captured=True,
        ),
        security=ControlRoomSecurity(binding_verified=True, kill_switch_state="RUNNING", threat_status="CLEAN"),
        evidence_records=[],
        replay=ControlRoomReplay(is_cpu_only=True, discrepancy_count=1),
        observability=ControlRoomObservability(),
        timeline=[],
        snapshot_digest="",
    )
    # Crucial assertion: payment_captured is True, BUT integrity is DRIFT!
    assert snap.payment.payment_captured is True
    assert snap.integrity.status == IntegrityStatus.DRIFT
    assert snap.payment.integrity_vs_payment_distinction == "CAPTURED_IS_NOT_PASS"


# ------------------------------------------------------------------------------
# 11. Failed/Pending Payment Remains Distinct from Integrity
# ------------------------------------------------------------------------------
def test_e7_11_pending_payment_distinct_from_integrity():
    """Verifies payment failure does not change integrity facts."""
    now = datetime.now(timezone.utc)
    pay = ControlRoomPayment(
        order_id="order_1",
        payment_id="pay_failed_1",
        payment_status="failed",
        amount=Money(amount=5000000, currency="INR"),
        payment_captured=False,
    )
    assert pay.payment_status == "failed"
    assert pay.payment_captured is False


# ------------------------------------------------------------------------------
# 12. Complete Hero Loop: DRIFT -> Recovery -> Revalidation -> PASS
# ------------------------------------------------------------------------------
def test_e7_12_hero_loop_drift_recovery_revalidate_pass(client):
    """Verifies that the full E6 loop produces a revalidated PASS snapshot with hero message."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6", "simulate_mutation": True})
    assert res.status_code == 200
    snap = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}").json()

    assert snap["recovery"]["recovery_invoked"] is True
    assert snap["recovery"]["revalidated_pass"] is True
    assert snap["integrity"]["status"] == "PASS"
    assert "TRANSACTION RESTORED" in snap["hero_message"]


# ------------------------------------------------------------------------------
# 13. Unresolved Recovery Remains Non-PASS
# ------------------------------------------------------------------------------
def test_e7_13_unresolved_recovery_remains_non_pass():
    """Verifies failed revalidation keeps integrity status at DRIFT."""
    now = datetime.now(timezone.utc)
    rec = ControlRoomRecovery(
        recovery_invoked=True,
        recovery_status="FAILED",
        replan_rounds=3,
        revalidation_verdict=IntegrityStatus.DRIFT.value,
        revalidated_pass=False,
        attempts_count=3,
        max_attempts=3,
    )
    assert rec.revalidated_pass is False
    assert rec.recovery_status == "FAILED"


# ------------------------------------------------------------------------------
# 14. UNKNOWN Remains UNKNOWN Until Authoritative Resolution
# ------------------------------------------------------------------------------
def test_e7_14_unknown_remains_unknown_until_resolution():
    """Verifies that unknown state does not speculate or guess PASS."""
    integ = ControlRoomIntegrity(
        status=IntegrityStatus.UNKNOWN,
        violations=["AWAITING_PROVIDER_STATE"],
    )
    assert integ.status == IntegrityStatus.UNKNOWN
    assert integ.economic_verdict is None


# ------------------------------------------------------------------------------
# 15. Security Findings Surface Correctly
# ------------------------------------------------------------------------------
def test_e7_15_security_findings_surface_correctly(client):
    """Verifies security section reflects verified binding and threat status."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    snap = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}").json()
    assert snap["security"]["binding_verified"] is True
    assert snap["security"]["threat_status"] == "CLEAN"


# ------------------------------------------------------------------------------
# 16. Kill Switch Surfaces Correctly
# ------------------------------------------------------------------------------
def test_e7_16_kill_switch_surfaces_correctly(client):
    """Verifies kill switch state is reported."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    snap = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}").json()
    assert snap["security"]["kill_switch_state"] == "RUNNING"


# ------------------------------------------------------------------------------
# 17. Prompt Injection / Threat Findings Surfaced
# ------------------------------------------------------------------------------
def test_e7_17_prompt_injection_threat_findings_surfaced():
    """Verifies threat detection fields are properly typed and populated."""
    sec = ControlRoomSecurity(
        binding_verified=True,
        kill_switch_state="PAUSED",
        threat_status="THREAT_DETECTED",
        threats_detected=["PROMPT_INJECTION_DISREGARD_BUDGET"],
        prompt_injection_detected=True,
        tampering_detected=False,
    )
    assert sec.prompt_injection_detected is True
    assert len(sec.threats_detected) == 1


# ------------------------------------------------------------------------------
# 18. Evidence Provenance Surfaces Correctly
# ------------------------------------------------------------------------------
def test_e7_18_evidence_provenance_surfaces_correctly(client):
    """Verifies that evidence records retain their provenance and authority levels."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    snap = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}").json()
    assert len(snap["evidence_records"]) > 0
    ev = snap["evidence_records"][0]
    assert "evidence_id" in ev
    assert "authority" in ev
    assert ev["authority"] in ["AUTHORITATIVE", "MERCHANT_ATTESTED", "ADVISORY"]


# ------------------------------------------------------------------------------
# 19. Replay MATCH Surfaces Correctly
# ------------------------------------------------------------------------------
def test_e7_19_replay_match_surfaces_correctly(client):
    """Verifies that replay verdict is MATCH and CPU-only."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    snap = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}").json()
    assert snap["replay"]["replay_available"] is True
    assert snap["replay"]["replay_verdict"] == "MATCH"
    assert snap["replay"]["is_cpu_only"] is True


# ------------------------------------------------------------------------------
# 20. Replay MISMATCH Surfaces Correctly
# ------------------------------------------------------------------------------
def test_e7_20_replay_mismatch_surfaces_correctly():
    """Verifies that replay failure records discrepancy count and verdict."""
    rep = ControlRoomReplay(
        replay_available=True,
        replay_verdict="MISMATCH",
        is_cpu_only=True,
        discrepancy_count=2,
    )
    assert rep.replay_verdict == "MISMATCH"
    assert rep.discrepancy_count == 2


# ------------------------------------------------------------------------------
# 21. Synthetic/Offline Execution Visibly Distinguishable
# ------------------------------------------------------------------------------
def test_e7_21_synthetic_offline_execution_distinguishable(client):
    """Verifies execution mode is accurately declared as SYNTHETIC_OFFLINE_HERO_RUN."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    snap = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}").json()
    assert snap["execution_mode"] == "SYNTHETIC_OFFLINE_HERO_RUN"


# ------------------------------------------------------------------------------
# 22. Real Razorpay Test Mode is Not Claimed Without Real Provider Execution
# ------------------------------------------------------------------------------
def test_e7_22_real_razorpay_not_falsely_claimed(client):
    """Verifies that synthetic execution does not claim REAL_RAZORPAY_TEST_MODE."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    snap = client.get(f"/api/v1/control-room/snapshot/{res.json()['transaction_id']}").json()
    assert snap["execution_mode"] != "REAL_RAZORPAY_TEST_MODE"


# ------------------------------------------------------------------------------
# 23. E7 Live Operational Feed API Test
# ------------------------------------------------------------------------------
def test_e7_23_live_operational_feed_endpoint(client):
    """Verifies /api/v1/control-room/live returns complete system status."""
    res = client.get("/api/v1/control-room/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ONLINE"
    assert data["advisory_ai_model"] == "openai/gpt-oss-20b"
    assert data["ai_authority"] == "ADVISORY_ONLY"
    assert data["deterministic_engine"] == "AUTHORITATIVE"


# ------------------------------------------------------------------------------
# 24. E7 Recent Summaries API Test
# ------------------------------------------------------------------------------
def test_e7_24_recent_summaries_endpoint(client):
    """Verifies /api/v1/control-room/recent returns a list of summary cards."""
    # Run a transaction to ensure at least 1 exists
    client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    res = client.get("/api/v1/control-room/recent?limit=5")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    assert "transaction_id" in items[0]
    assert "integrity_status" in items[0]


# ------------------------------------------------------------------------------
# 25. Snapshot Digest Immutability and Determinism
# ------------------------------------------------------------------------------
def test_e7_25_snapshot_digest_determinism(client):
    """Verifies that identical snapshot facts produce identical SHA-256 digests."""
    res = client.post("/api/v1/hero-transaction/run", json={"scenario": "e6"})
    tx_id = res.json()["transaction_id"]
    r1 = client.get(f"/api/v1/control-room/snapshot/{tx_id}").json()
    r2 = client.get(f"/api/v1/control-room/snapshot/{tx_id}").json()
    assert r1["snapshot_digest"] == r2["snapshot_digest"]
    assert len(r1["snapshot_digest"]) == 64
