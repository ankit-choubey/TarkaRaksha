"""Adversarial and security test suite for I10 Operational Deployment Modes.

Verifies strict enforcement against:
1. LLM attempts to change mode.
2. Buyer agent attempts to change mode.
3. Merchant agent attempts to change mode.
4. TIX participant attempts to change mode.
5. Review approval reused across transactions.
6. Review approval reused across agents.
7. Review approval reused across merchants.
8. SHADOW mode accidentally triggering remediation.
9. GUARDED mode bypassing I9 execution safety.
10. HUMAN_REVIEW bypassing revalidation.
11. UNKNOWN becoming PASS through mode handling.
12. DRIFT being suppressed in SHADOW mode.
13. Policy version mismatch / verification.
14. Mode transition without required authority or reason.
15. Settled review mutation attempts.
16. Mode configuration immutability.
17. AI attempt to simulate human review approval.
18. Cross-transaction decision reuse.
"""
from datetime import datetime, timedelta, timezone
import pytest

from backend.app.domain.models.intent import IntentContract, IntentItem
from backend.app.domain.kill_switch.contracts import ExecutionBlockedError, KillSwitchState
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.negotiation.contracts import NegotiationState
from backend.app.domain.operational_mode.contracts import (
    HumanReviewDecision,
    HumanReviewRequiredError,
    HumanReviewStatus,
    OperationalAction,
    OperationalMode,
    OperationalModePolicy,
)
from backend.app.domain.operational_mode.policy import OperationalModeEngine
from backend.app.services.buyer.agent_service import BuyerAgentService
from backend.app.services.merchant.catalog_service import MerchantCatalogService
from backend.app.domain.merchant.contracts import MerchantResponse
from backend.app.services.negotiation.service import BoundedNegotiationService
from backend.app.services.operational_mode.service import OperationalModeService
from backend.app.services.tix import TIXExchangeService


def test_adv_01_llm_cannot_change_mode():
    """Attack 1: LLM attempts to change operational deployment mode."""
    service = OperationalModeService()
    with pytest.raises(PermissionError, match="contains unauthorized role keyword"):
        service.set_mode(
            new_mode=OperationalMode.SHADOW,
            changed_by="groq_llama3_agent_llm",
            reason="AI decided to bypass controls",
        )


def test_adv_02_buyer_agent_cannot_change_mode():
    """Attack 2: Buyer Agent attempts to change operational deployment mode."""
    service = OperationalModeService()
    with pytest.raises(PermissionError, match="contains unauthorized role keyword"):
        service.set_mode(
            new_mode=OperationalMode.SHADOW,
            changed_by="buyer_agent_primary",
            reason="Buyer agent attempting to disable enforcement",
        )


def test_adv_03_merchant_agent_cannot_change_mode():
    """Attack 3: Merchant Agent attempts to change operational deployment mode."""
    service = OperationalModeService()
    with pytest.raises(PermissionError, match="contains unauthorized role keyword"):
        service.set_mode(
            new_mode=OperationalMode.SHADOW,
            changed_by="merchant_agent_store_v1",
            reason="Merchant agent attempting to disable integrity checks",
        )


def test_adv_04_tix_participant_cannot_change_mode():
    """Attack 4: TIX protocol participant attempts to change operational deployment mode."""
    service = OperationalModeService()
    with pytest.raises(PermissionError, match="contains unauthorized role keyword"):
        service.set_mode(
            new_mode=OperationalMode.GUARDED,
            changed_by="tix_exchange_bridge_node",
            reason="TIX node attempting to alter mode policy",
        )


def test_adv_05_review_approval_cannot_be_reused_across_transactions():
    """Attack 5: Cross-transaction review approval reuse is strictly blocked."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    )
    req = service.create_review_requirement(
        transaction_id="tx_legit_100",
        intent_id="intent_100",
        agent_id="agent_100",
        merchant_id="merchant_100",
        reason="High value checkout",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    # Attack: An attacker tries to submit an approval targeting tx_attacker_999 using rev_id of tx_legit_100
    decision = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_attacker_999",
        decision=HumanReviewStatus.APPROVED,
        reviewer_id="human_compliance_officer_alice",
        rationale="Approved legitimate checkout",
    )

    with pytest.raises(ValueError, match="Cross-transaction review approval reuse detected and rejected"):
        service.submit_human_review(decision)


def test_adv_06_review_approval_cannot_be_reused_across_agents():
    """Attack 6: Cross-agent review reuse is strictly blocked."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    )
    req = service.create_review_requirement(
        transaction_id="tx_test_200",
        intent_id="intent_200",
        agent_id="agent_legit_alpha",
        merchant_id="merchant_200",
        reason="High value checkout",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    decision = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_test_200",
        decision=HumanReviewStatus.APPROVED,
        reviewer_id="human_compliance_officer_alice",
        rationale="Approved checkout",
    )

    with pytest.raises(ValueError, match="Agent mismatch"):
        service.submit_human_review(decision, expected_agent_id="agent_rogue_beta")


def test_adv_07_review_approval_cannot_be_reused_across_merchants():
    """Attack 7: Cross-merchant review reuse is strictly blocked."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    )
    req = service.create_review_requirement(
        transaction_id="tx_test_300",
        intent_id="intent_300",
        agent_id="agent_300",
        merchant_id="merchant_apple_store",
        reason="High value checkout",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    decision = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_test_300",
        decision=HumanReviewStatus.APPROVED,
        reviewer_id="human_compliance_officer_alice",
        rationale="Approved checkout",
    )

    with pytest.raises(ValueError, match="Merchant mismatch"):
        service.submit_human_review(decision, expected_merchant_id="merchant_phishing_corp")


def test_adv_08_shadow_mode_strictly_blocks_automated_remediation():
    """Attack 8: SHADOW mode must never perform automated remediation or compensatory actions."""
    op_service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.SHADOW)
    )
    buyer_svc = BuyerAgentService()
    merch_svc = MerchantCatalogService(merchant_id="merchant_store_1")
    tix_svc = TIXExchangeService()
    negotiation_service = BoundedNegotiationService(
        buyer_service=buyer_svc,
        merchant_service=merch_svc,
        tix_service=tix_svc,
        operational_mode_service=op_service,
    )

    ref_time = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    intent = IntentContract(
        intent_id="intent_neg_shadow",
        issued_by="buyer_alice",
        items=[
            IntentItem(
                item_id="i1",
                sku="SERVER-256",
                name="Server 256GB",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
        max_total=Money(amount=5000000, currency="INR"),
        issued_at=ref_time,
        expires_at=ref_time + timedelta(hours=2),
    )

    initial_resp = MerchantResponse(
        response_id="resp_00",
        merchant_id="merchant_store_1",
        request_id="req_00",
        intent_id=intent.intent_id,
        transaction_id="tx_shadow_neg",
        is_success=True,
        total_amount=Money(amount=6000000, currency="INR"),  # Exceeds max_total (drift)
        offer_created_at=ref_time,
        offer_expires_at=ref_time + timedelta(hours=1),
    )

    session = negotiation_service.execute_bounded_remediation(
        intent=intent,
        transaction_id="tx_shadow_neg",
        initial_merchant_response=initial_resp,
        initial_evidence=[],
        events=[],
        reference_time=ref_time,
    )

    assert session.state == NegotiationState.ABSTAINED
    assert session.final_verdict == IntegrityStatus.DRIFT
    assert "SHADOW mode active" in session.original_violations[0]
    assert "disabled in SHADOW mode" in session.termination_reason


def test_adv_09_guarded_mode_cannot_bypass_i9_killed_state():
    """Attack 9: GUARDED mode cannot bypass an active I9 KILLED state."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.GUARDED)
    )
    eval_res = service.evaluate_transaction(
        transaction_id="tx_killed_400",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.KILLED,
        amount=Money(amount=5000, currency="INR"),
    )

    assert eval_res.can_execute_payment is False
    assert eval_res.action == OperationalAction.TRIGGER_SAFETY_CONTROL

    with pytest.raises(ExecutionBlockedError, match="blocked by operational mode policy"):
        service.assert_can_execute_payment("tx_killed_400", eval_res)


def test_adv_10_human_review_approval_does_not_bypass_revalidation():
    """Attack 10: Human approval on DRIFT does NOT automatically allow execution without revalidation."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    )
    req = service.create_review_requirement(
        transaction_id="tx_drift_500",
        intent_id="intent_500",
        agent_id="agent_500",
        merchant_id="merchant_500",
        reason="Drift detected during payment attempt",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    # Human approves
    decision = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_drift_500",
        decision=HumanReviewStatus.APPROVED,
        reviewer_id="human_supervisor_bob",
        rationale="Manager approved, but must be revalidated",
    )
    service.submit_human_review(decision)

    # Evaluating the transaction still sees DRIFT
    eval_res = service.evaluate_transaction(
        transaction_id="tx_drift_500",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    # Human review approved on DRIFT must require revalidation, cannot execute payment directly
    assert eval_res.can_execute_payment is False
    assert eval_res.action == OperationalAction.BLOCK_EXECUTION
    assert req.revalidation_required is True
    assert "revalidation required" in eval_res.reason


def test_adv_11_unknown_never_becomes_pass_in_any_mode():
    """Attack 11: UNKNOWN must never convert into PASS in any operational mode."""
    # SHADOW
    shadow_eval = OperationalModeEngine.evaluate(
        policy=OperationalModePolicy(mode=OperationalMode.SHADOW),
        transaction_id="tx_unk_1",
        integrity_status=IntegrityStatus.UNKNOWN,
        kill_switch_state=KillSwitchState.RUNNING,
    )
    assert shadow_eval.integrity_status == IntegrityStatus.UNKNOWN
    assert shadow_eval.action == OperationalAction.OBSERVE_ONLY

    # GUARDED
    guarded_eval = OperationalModeEngine.evaluate(
        policy=OperationalModePolicy(mode=OperationalMode.GUARDED),
        transaction_id="tx_unk_2",
        integrity_status=IntegrityStatus.UNKNOWN,
        kill_switch_state=KillSwitchState.RUNNING,
    )
    assert guarded_eval.integrity_status == IntegrityStatus.UNKNOWN
    assert guarded_eval.can_execute_payment is False
    assert guarded_eval.action == OperationalAction.BLOCK_EXECUTION

    # HUMAN_REVIEW
    hr_eval = OperationalModeEngine.evaluate(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW),
        transaction_id="tx_unk_3",
        integrity_status=IntegrityStatus.UNKNOWN,
        kill_switch_state=KillSwitchState.RUNNING,
    )
    assert hr_eval.integrity_status == IntegrityStatus.UNKNOWN
    assert hr_eval.can_execute_payment is False
    assert hr_eval.action == OperationalAction.REQUIRE_HUMAN_REVIEW


def test_adv_12_drift_is_not_suppressed_in_shadow_mode():
    """Attack 12: DRIFT verdict is not suppressed or overwritten to PASS in SHADOW mode."""
    shadow_eval = OperationalModeEngine.evaluate(
        policy=OperationalModePolicy(mode=OperationalMode.SHADOW),
        transaction_id="tx_drift_shadow",
        integrity_status=IntegrityStatus.DRIFT,
        kill_switch_state=KillSwitchState.RUNNING,
    )
    assert shadow_eval.integrity_status == IntegrityStatus.DRIFT
    assert shadow_eval.enforcement_active is False
    assert shadow_eval.action == OperationalAction.OBSERVE_ONLY
    assert "evaluated as DRIFT" in shadow_eval.reason


def test_adv_13_policy_empty_reason_and_audit():
    """Attack 13: Operational mode change without deterministic reason is rejected."""
    service = OperationalModeService()
    with pytest.raises(ValueError, match="clear deterministic reason must be provided"):
        service.set_mode(
            new_mode=OperationalMode.SHADOW,
            changed_by="admin_alice",
            reason="   ",
        )


def test_adv_14_ai_cannot_simulate_human_review_approval():
    """Attack 14: AI or autonomous agent cannot submit a human review approval."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    )
    req = service.create_review_requirement(
        transaction_id="tx_ai_sim_600",
        intent_id="intent_600",
        agent_id="agent_600",
        merchant_id="merchant_600",
        reason="Needs human review",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    decision = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_ai_sim_600",
        decision=HumanReviewStatus.APPROVED,
        reviewer_id="ai_autonomous_evaluator_bot",
        rationale="AI judged the checkout to be safe",
    )

    with pytest.raises(PermissionError, match="contains forbidden agent/model keyword"):
        service.submit_human_review(decision)


def test_adv_15_settled_review_cannot_be_mutated():
    """Attack 15: Settled review requirement cannot be altered or re-decided."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    )
    req = service.create_review_requirement(
        transaction_id="tx_settled_700",
        intent_id="intent_700",
        agent_id="agent_700",
        merchant_id="merchant_700",
        reason="Needs human review",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    first_decision = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_settled_700",
        decision=HumanReviewStatus.REJECTED,
        reviewer_id="human_officer_charlie",
        rationale="Suspicious address",
    )
    service.submit_human_review(first_decision)

    # Second attempt to overturn rejection
    second_decision = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_settled_700",
        decision=HumanReviewStatus.APPROVED,
        reviewer_id="human_officer_david",
        rationale="Overriding previous rejection",
    )
    with pytest.raises(ValueError, match="already settled"):
        service.submit_human_review(second_decision)


def test_adv_16_policy_model_immutability():
    """Attack 16: Pydantic frozen configuration cannot be mutated in place."""
    policy = OperationalModePolicy(mode=OperationalMode.GUARDED)
    with pytest.raises(Exception):
        policy.mode = OperationalMode.SHADOW


def test_adv_17_human_review_rejection_blocks_payment_execution():
    """Attack 17: Rejected human review strictly blocks payment assertion."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    )
    req = service.create_review_requirement(
        transaction_id="tx_rej_800",
        intent_id="intent_800",
        agent_id="agent_800",
        merchant_id="merchant_800",
        reason="Manual check required",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    decision = HumanReviewDecision(
        review_id=req.review_id,
        transaction_id="tx_rej_800",
        decision=HumanReviewStatus.REJECTED,
        reviewer_id="human_officer_eva",
        rationale="Payment rejected due to policy breach",
    )
    service.submit_human_review(decision)

    eval_res = service.evaluate_transaction(
        transaction_id="tx_rej_800",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    assert eval_res.can_execute_payment is False
    assert eval_res.action == OperationalAction.BLOCK_EXECUTION

    with pytest.raises(ExecutionBlockedError, match="blocked by operational mode policy"):
        service.assert_can_execute_payment("tx_rej_800", eval_res)


def test_adv_18_pending_review_raises_human_review_required():
    """Attack 18: Pending review stops execution with HumanReviewRequiredError, not silent pass."""
    service = OperationalModeService(
        policy=OperationalModePolicy(mode=OperationalMode.HUMAN_REVIEW)
    )
    service.create_review_requirement(
        transaction_id="tx_pend_900",
        intent_id="intent_900",
        agent_id="agent_900",
        merchant_id="merchant_900",
        reason="Manual check required",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    eval_res = service.evaluate_transaction(
        transaction_id="tx_pend_900",
        integrity_status=IntegrityStatus.PASS,
        kill_switch_state=KillSwitchState.RUNNING,
    )

    assert eval_res.can_execute_payment is False
    assert eval_res.action == OperationalAction.REQUIRE_HUMAN_REVIEW

    with pytest.raises(HumanReviewRequiredError, match="Payment execution held in HUMAN_REVIEW mode"):
        service.assert_can_execute_payment("tx_pend_900", eval_res)
