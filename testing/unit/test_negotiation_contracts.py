"""Unit tests for I7 — Bounded Agentic Negotiation Contracts.

Validates:
1. NegotiationPolicy bounds and immutability.
2. NegotiationRoundRecord fields and strict validation.
3. NegotiationSession immutability, non-empty identifiers, and state management.
4. NegotiationState and NegotiationViolationCode complete enum mappings.
"""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.money import Money
from backend.app.domain.negotiation import (
    NegotiationPolicy,
    NegotiationRoundRecord,
    NegotiationSession,
    NegotiationState,
    NegotiationViolationCode,
)


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def test_negotiation_policy_defaults_and_validation():
    pol = NegotiationPolicy()
    assert pol.max_rounds == 3
    assert pol.max_replans == 3
    assert pol.allow_substitutions is True
    assert pol.allow_partial is False
    assert pol.timeout_seconds == 300

    # Test invalid bounds
    with pytest.raises(ValidationError):
        NegotiationPolicy(max_rounds=0)

    with pytest.raises(ValidationError):
        NegotiationPolicy(max_rounds=11)

    with pytest.raises(ValidationError):
        NegotiationPolicy(max_replans=-1)


def test_negotiation_round_record_instantiation(base_time: datetime):
    rec = NegotiationRoundRecord(
        round_number=1,
        transaction_id="tx_001",
        intent_id="intent_001",
        attempt_id="att_1",
        state=NegotiationState.REPLAN_REQUESTED,
        buyer_proposal_id="prop_001",
        merchant_response_id="resp_001",
        proposed_sku="SERVER-256",
        proposed_quantity=1,
        offered_total=Money(amount=4900000, currency="INR"),
        drift_violations=["MAX_TOTAL_EXCEEDED"],
        mrdp_id="mrdp_001",
        tix_message_ids=["tix_01", "tix_02"],
        timestamp=base_time,
        rationale="Initial counter-offer evaluation",
    )

    assert rec.round_number == 1
    assert rec.proposed_sku == "SERVER-256"
    assert rec.offered_total == Money(amount=4900000, currency="INR")
    assert rec.state == NegotiationState.REPLAN_REQUESTED

    # Immutability
    with pytest.raises(ValidationError):
        rec.round_number = 2  # type: ignore


def test_negotiation_round_record_validations(base_time: datetime):
    # Invalid round number (< 1)
    with pytest.raises(ValidationError):
        NegotiationRoundRecord(
            round_number=0,
            transaction_id="tx_001",
            intent_id="intent_001",
            attempt_id="att_1",
            state=NegotiationState.DRIFT_DETECTED,
            timestamp=base_time,
        )

    # Naive timestamp
    with pytest.raises(ValidationError):
        NegotiationRoundRecord(
            round_number=1,
            transaction_id="tx_001",
            intent_id="intent_001",
            attempt_id="att_1",
            state=NegotiationState.DRIFT_DETECTED,
            timestamp=datetime(2026, 9, 5, 12, 0, 0),  # naive
        )


def test_negotiation_session_instantiation(base_time: datetime):
    sess = NegotiationSession(
        session_id="sess_001",
        transaction_id="tx_001",
        intent_id="intent_001",
        buyer_agent_id="buyer_agent_1",
        merchant_id="merchant_1",
        state=NegotiationState.COMPLETED,
        current_round=1,
        policy=NegotiationPolicy(),
        rounds=[],
        original_verdict=IntegrityStatus.DRIFT,
        original_violations=["Price exceeded"],
        final_verdict=IntegrityStatus.PASS,
        is_settled=True,
        termination_reason="Agreement reached within budget constraints",
        created_at=base_time,
        updated_at=base_time,
    )

    assert sess.session_id == "sess_001"
    assert sess.is_settled is True
    assert sess.state == NegotiationState.COMPLETED

    # Immutability
    with pytest.raises(ValidationError):
        sess.is_settled = False  # type: ignore


@pytest.mark.parametrize(
    "field",
    ["session_id", "transaction_id", "intent_id", "buyer_agent_id", "merchant_id"],
)
def test_negotiation_session_empty_id_rejected(base_time: datetime, field: str):
    data = {
        "session_id": "sess_001",
        "transaction_id": "tx_001",
        "intent_id": "intent_001",
        "buyer_agent_id": "buyer_agent_1",
        "merchant_id": "merchant_1",
        "state": NegotiationState.NOT_STARTED,
        "created_at": base_time,
        "updated_at": base_time,
    }
    data[field] = "   "
    with pytest.raises(ValidationError):
        NegotiationSession(**data)


def test_negotiation_enums_complete():
    expected_states = {
        "NOT_STARTED",
        "DRIFT_DETECTED",
        "REPLAN_REQUESTED",
        "COUNTER_OFFER_RECEIVED",
        "REVALIDATING",
        "COMPLETED",
        "ABSTAINED",
        "ESCALATED",
        "FAILED",
    }
    assert {s.value for s in NegotiationState} == expected_states

    expected_violations = {
        "MAX_ROUNDS_EXCEEDED",
        "MAX_REPLANS_EXCEEDED",
        "BUDGET_ESCALATION_ATTEMPT",
        "UNAUTHORIZED_SUBSTITUTION",
        "QUANTITY_ESCALATION",
        "CURRENCY_MUTATION",
        "INTENT_MISMATCH",
        "TRANSACTION_MISMATCH",
        "ATTEMPT_REUSE",
        "PASS_INJECTION_ATTEMPT",
        "UNAUTHORIZED_PAYMENT_CLAIM",
        "TIX_BYPASS",
        "HISTORICAL_PROPOSAL_MUTATED",
    }
    assert {v.value for v in NegotiationViolationCode} == expected_violations
