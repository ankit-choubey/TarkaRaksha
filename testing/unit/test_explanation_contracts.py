"""Unit tests for I21 Explanation Domain Contracts."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.explanation.contracts import (
    ClaimType,
    EvidenceReference,
    ExplanationClaim,
    ExplanationContext,
    ExplanationResult,
    ExplanationValidationResult,
    FindingCategory,
)
from backend.app.domain.kill_switch.contracts import KillSwitchState, KillTrigger
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource, IntegrityStatus


def test_evidence_reference_contract():
    ref = EvidenceReference(
        evidence_id="ev_amt_001",
        field_name="amount",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        observed_value=150000,
        expected_value=150000,
        is_authoritative=True,
        description="Observed razorpay payment amount",
    )
    assert ref.evidence_id == "ev_amt_001"
    assert ref.is_authoritative is True

    # Immutability
    with pytest.raises(ValidationError):
        ref.observed_value = 200000

    # Non-empty validation
    with pytest.raises(ValidationError):
        EvidenceReference(
            evidence_id="",
            field_name="amount",
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            observed_value=150000,
        )


def test_explanation_claim_contract():
    claim = ExplanationClaim(
        claim_id="claim_1",
        claim_text="Amount matched authorized budget.",
        evidence_refs=["ev_amt_001"],
        authority_tier=EvidenceAuthority.AUTHORITATIVE,
        claim_type=ClaimType.FACT,
        category=FindingCategory.ECONOMIC,
    )
    assert claim.claim_id == "claim_1"
    assert claim.claim_type == ClaimType.FACT
    assert claim.category == FindingCategory.ECONOMIC

    # Immutability
    with pytest.raises(ValidationError):
        claim.claim_text = "Modified claim"


def test_explanation_context_contract():
    now = datetime.now(timezone.utc)
    ev_ref = EvidenceReference(
        evidence_id="ev_amt_001",
        field_name="amount",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        observed_value=150000,
        expected_value=150000,
    )
    ctx = ExplanationContext(
        context_id="ctx_001",
        transaction_id="tx_001",
        intent_id="intent_001",
        deterministic_decision=IntegrityStatus.PASS,
        decision_reason="All rules passed",
        kill_switch_state=KillSwitchState.RUNNING,
        evidence_references=[ev_ref],
        created_at=now,
    )
    assert ctx.valid_evidence_ids == {"ev_amt_001"}
    assert ctx.get_evidence_ref("ev_amt_001") == ev_ref
    assert ctx.get_evidence_ref("ev_unknown") is None

    # Timezone validation
    with pytest.raises(ValidationError):
        ExplanationContext(
            context_id="ctx_002",
            transaction_id="tx_001",
            intent_id="intent_001",
            deterministic_decision=IntegrityStatus.PASS,
            decision_reason="Reason",
            kill_switch_state=KillSwitchState.RUNNING,
            created_at=datetime.now(),  # naive
        )


def test_explanation_validation_result_contract():
    now = datetime.now(timezone.utc)
    res = ExplanationValidationResult(
        is_valid=True,
        violations=[],
        validated_at=now,
    )
    assert res.is_valid is True
    assert len(res.violations) == 0


def test_explanation_result_contract():
    now = datetime.now(timezone.utc)
    val_res = ExplanationValidationResult(
        is_valid=True,
        violations=[],
        validated_at=now,
    )
    exp = ExplanationResult(
        explanation_id="exp_001",
        transaction_id="tx_001",
        deterministic_decision=IntegrityStatus.PASS,
        execution_state=KillSwitchState.RUNNING,
        summary="All verified cleanly.",
        claims=[],
        mismatches=[],
        missing_evidence=[],
        uncertainties=[],
        recommended_next_action="Execute transaction",
        validation_result=val_res,
        is_fallback=False,
        generated_at=now,
    )
    assert exp.explanation_id == "exp_001"
    assert exp.is_fallback is False
    assert exp.deterministic_decision == IntegrityStatus.PASS

    # Serialization round-trip
    dumped = exp.model_dump_json()
    loaded = ExplanationResult.model_validate_json(dumped)
    assert loaded.explanation_id == exp.explanation_id


def test_context_builder_reproducibility():
    from backend.app.services.explanation.context_builder import ExplanationContextBuilder
    from backend.app.domain.models import IntentContract, IntentItem, Money
    from datetime import timedelta

    ref_time = datetime(2026, 9, 5, 14, 0, 0, tzinfo=timezone.utc)
    intent = IntentContract(
        intent_id="intent_repro_1",
        issued_by="agent_1",
        max_total=Money(amount=20000, currency="INR"),
        currency="INR",
        items=[
            IntentItem(
                item_id="item_repro_1",
                sku="SKU-REPRO",
                name="Reproducibility Item",
                quantity=1,
                unit_price=Money(amount=20000, currency="INR"),
                total_price=Money(amount=20000, currency="INR"),
            )
        ],
        issued_at=ref_time,
        expires_at=ref_time + timedelta(minutes=15),
    )

    ctx1 = ExplanationContextBuilder.build_context(
        transaction_id="tx_repro_1",
        intent=intent,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=ref_time,
    )
    ctx2 = ExplanationContextBuilder.build_context(
        transaction_id="tx_repro_1",
        intent=intent,
        kill_switch_state=KillSwitchState.RUNNING,
        reference_time=ref_time,
    )

    # Identical deterministic inputs produce identical evidence references
    assert [ref.model_dump() for ref in ctx1.evidence_references] == [ref.model_dump() for ref in ctx2.evidence_references]
    assert ctx1.deterministic_decision == ctx2.deterministic_decision
    assert ctx1.kill_switch_state == ctx2.kill_switch_state
    assert ctx1.missing_evidence_fields == ctx2.missing_evidence_fields


def test_context_builder_handles_i8_and_i9():
    from backend.app.services.explanation.context_builder import ExplanationContextBuilder
    from backend.app.domain.binding.contracts import BindingVerificationOutcome, BindingViolationCode
    from backend.app.domain.kill_switch.contracts import KillSwitchRecord, ExecutionDecision
    from backend.app.domain.models import IntentContract, IntentItem, Money
    from datetime import timedelta

    ref_time = datetime(2026, 9, 5, 14, 0, 0, tzinfo=timezone.utc)
    intent = IntentContract(
        intent_id="intent_i8_i9",
        issued_by="agent_1",
        max_total=Money(amount=20000, currency="INR"),
        currency="INR",
        items=[
            IntentItem(
                item_id="item_1",
                sku="SKU-1",
                name="Item 1",
                quantity=1,
                unit_price=Money(amount=20000, currency="INR"),
                total_price=Money(amount=20000, currency="INR"),
            )
        ],
        issued_at=ref_time,
        expires_at=ref_time + timedelta(minutes=15),
    )

    binding_outcome = BindingVerificationOutcome(
        is_valid=False,
        status=IntegrityStatus.DRIFT,
        violations=[BindingViolationCode.ORDER_MISMATCH],
        details={"expected_order": "order_A", "observed_order": "order_B"},
        explanation="Order ID mismatch detected",
        verified_at=ref_time,
    )

    ks_record = KillSwitchRecord(
        record_id="rec_ks_001",
        transaction_id="tx_i8_i9",
        prior_state=KillSwitchState.RUNNING,
        resulting_state=KillSwitchState.KILLED,
        decision=ExecutionDecision.BLOCK,
        trigger=KillTrigger.BINDING_VIOLATION,
        reason="Binding violation from I8",
        timestamp=ref_time,
        revalidation_requirements=["Verify order binding with merchant"],
    )

    ctx = ExplanationContextBuilder.build_context(
        transaction_id="tx_i8_i9",
        intent=intent,
        binding_outcome=binding_outcome,
        kill_switch_state=KillSwitchState.KILLED,
        kill_switch_record=ks_record,
        reference_time=ref_time,
    )

    assert ctx.kill_switch_state == KillSwitchState.KILLED
    assert ctx.kill_switch_trigger == KillTrigger.BINDING_VIOLATION
    assert ctx.binding_violations == ["ORDER_MISMATCH"]
    assert "Verify order binding with merchant" in ctx.revalidation_requirements
    # Check that binding evidence reference and KS evidence reference exist
    assert any("binding" in ref.field_name for ref in ctx.evidence_references)
    assert any("kill_switch" in ref.field_name for ref in ctx.evidence_references)

