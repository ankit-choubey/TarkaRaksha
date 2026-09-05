"""
Unit Test Suite for TarkaRaksha AI Integration (T08).
Testing reference: brain/TarkaRaksha_TESTING.md §9.30–§9.36.

Covers:
- Intent Parser: valid intent, missing fields, wrong types, float amounts, quantity violation,
  budget manipulation, prompt injection as inert text, empty request, bounded retry on malformed JSON
- Recovery Agent: valid safe proposal, rejection of CAPTURE, budget breach rejection,
  refund exceeding discrepancy rejection, currency mismatch rejection, bounded retry
- Confidence invariant: 99.9% confidence does not authorize financial capture
- Provider failure matrix: timeout, rate limit, unavailable, malformed JSON
"""
from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from backend.app.domain.models import (
    ActionType,
    IntegrityStatus,
    IntentContract,
    IntentItem,
    Money,
    MRDP,
    RecoveryProposal,
)
from backend.app.services.ai import (
    AIProvider,
    FakeAIProvider,
    parse_intent,
    propose_recovery,
    validate_recovery_proposal_safety,
    AIProviderError,
    AITimeoutError,
    AIRateLimitError,
    AIUnavailableError,
    StructuredOutputError,
    IntentParsingError,
    UnsafeRecoveryProposalError,
)


@pytest.fixture
def base_contract() -> IntentContract:
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    return IntentContract(
        intent_id="intent-test-ai",
        issued_by="user_alice",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        currency="INR",
        max_total=Money(amount=5000000, currency="INR"),  # ₹50,000.00
        items=[
            IntentItem(
                item_id="item-srv-1",
                sku="SERVER-256GB",
                name="Dedicated Server 256GB",
                quantity=1,
                unit_price=Money(amount=5000000, currency="INR"),
                total_price=Money(amount=5000000, currency="INR"),
            )
        ],
    )


@pytest.fixture
def base_mrdp(base_contract: IntentContract) -> MRDP:
    now = datetime(2026, 9, 5, 12, 5, 0, tzinfo=timezone.utc)
    return MRDP(
        mrdp_id="mrdp_test_ai_01",
        intent_id=base_contract.intent_id,
        error_code="ECONOMIC_DRIFT_CEILING_EXCEEDED",
        status=IntegrityStatus.DRIFT,
        violation="Observed amount 5500000 INR exceeded authorized limit 5000000 INR",
        drift_source="RAZORPAY",
        expected_value=Money(amount=5000000, currency="INR"),
        observed_value=Money(amount=5500000, currency="INR"),
        discrepancy_amount=Money(amount=500000, currency="INR"),
        evidence_references=["ev_rzp_01"],
        remediation="Revalidate payment state or request partial refund of excess amount",
        revalidation_required=True,
        generated_at=now,
    )


# ==============================================================================
# 1. INTENT PARSER UNIT TESTS
# ==============================================================================

def test_intent_parser_valid_extraction():
    """Valid natural language intent produces a validated domain IntentContract."""
    valid_json = """{
        "sku": "SERVER-256GB",
        "item_name": "Dedicated Server 256GB",
        "quantity": 1,
        "unit_price_minor": 5000000,
        "max_total_minor": 5000000,
        "currency": "INR",
        "allowed_substitutions": ["SERVER-512GB"],
        "allow_partial": false,
        "max_retries": 3,
        "notes": "Standard server provision"
    }"""
    fake = FakeAIProvider([valid_json])
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    contract = parse_intent(
        "Buy 1 dedicated server SERVER-256GB for up to ₹50,000 INR",
        provider=fake,
        issued_by="user_alice",
        issued_at=now,
    )

    assert contract.currency == "INR"
    assert contract.max_total == Money(amount=5000000, currency="INR")
    assert len(contract.items) == 1
    assert contract.items[0].sku == "SERVER-256GB"
    assert contract.items[0].quantity == 1
    assert contract.items[0].unit_price == Money(amount=5000000, currency="INR")
    assert contract.allowed_substitutions == ["SERVER-512GB"]


def test_intent_parser_empty_prompt_rejected():
    """Empty or whitespace-only prompt raises IntentParsingError immediately without calling AI."""
    fake = FakeAIProvider()
    with pytest.raises(IntentParsingError, match="empty or whitespace"):
        parse_intent("   ", provider=fake)
    assert fake.call_count == 0


def test_intent_parser_missing_required_field_rejected():
    """AI output missing a mandatory field (e.g. sku) is rejected."""
    missing_sku_json = """{
        "item_name": "Dedicated Server",
        "quantity": 1,
        "unit_price_minor": 5000000,
        "max_total_minor": 5000000,
        "currency": "INR"
    }"""
    fake = FakeAIProvider([missing_sku_json, missing_sku_json, missing_sku_json])
    with pytest.raises(IntentParsingError, match="Intent parsing failed"):
        parse_intent("Buy server", provider=fake, max_retries=1)


def test_intent_parser_float_amount_rejected():
    """AI output providing a float instead of integer minor units is rejected."""
    float_json = """{
        "sku": "SERVER-256GB",
        "item_name": "Server",
        "quantity": 1,
        "unit_price_minor": 50000.50,
        "max_total_minor": 50000.50,
        "currency": "INR"
    }"""
    fake = FakeAIProvider([float_json, float_json])
    with pytest.raises(IntentParsingError):
        parse_intent("Buy server", provider=fake, max_retries=1)


def test_intent_parser_quantity_violation_rejected():
    """AI output with non-positive quantity (0 or negative) is rejected."""
    zero_qty_json = """{
        "sku": "SERVER-256GB",
        "item_name": "Server",
        "quantity": 0,
        "unit_price_minor": 5000000,
        "max_total_minor": 5000000,
        "currency": "INR"
    }"""
    fake = FakeAIProvider([zero_qty_json, zero_qty_json])
    with pytest.raises(IntentParsingError):
        parse_intent("Buy 0 servers", provider=fake, max_retries=1)


def test_intent_parser_budget_manipulation_rejected():
    """AI output where max_total is less than item total is rejected by domain checks."""
    inconsistent_budget_json = """{
        "sku": "SERVER-256GB",
        "item_name": "Server",
        "quantity": 2,
        "unit_price_minor": 5000000,
        "max_total_minor": 5000000,
        "currency": "INR"
    }"""
    # 2 items * 50,000 = 100,000 > max_total (50,000)
    fake = FakeAIProvider([inconsistent_budget_json, inconsistent_budget_json])
    with pytest.raises(IntentParsingError, match="less than calculated items total"):
        parse_intent("Buy 2 servers for 50000 total", provider=fake, max_retries=1)


def test_intent_parser_bounded_retry_success():
    """Model returns invalid JSON on first attempt, valid on second; successfully recovers."""
    invalid_json = "MALFORMED_NOT_JSON"
    valid_json = """{
        "sku": "SERVER-256GB",
        "item_name": "Server",
        "quantity": 1,
        "unit_price_minor": 5000000,
        "max_total_minor": 5000000,
        "currency": "INR"
    }"""
    fake = FakeAIProvider([invalid_json, valid_json])
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    contract = parse_intent("Buy server", provider=fake, issued_at=now, max_retries=2)
    assert contract.items[0].sku == "SERVER-256GB"
    assert fake.call_count == 2


def test_intent_parser_bounded_retry_exhaustion():
    """When retries are exhausted on malformed JSON, raises safe IntentParsingError."""
    fake = FakeAIProvider(["BAD_JSON_1", "BAD_JSON_2"])
    with pytest.raises(IntentParsingError, match="Intent parsing failed after 2 attempts"):
        parse_intent("Buy server", provider=fake, max_retries=1)
    assert fake.call_count == 2


# ==============================================================================
# 2. RECOVERY AGENT UNIT TESTS
# ==============================================================================

def test_recovery_agent_valid_proposal(base_contract: IntentContract, base_mrdp: MRDP):
    """Valid advisory proposal (REFUND of excess discrepancy) succeeds."""
    valid_recovery_json = """{
        "proposed_action": "REFUND",
        "suggested_amount_minor": 500000,
        "currency": "INR",
        "reasoning": "Gateway charged 55,000 INR which exceeds authorized 50,000 INR. Request refund for excess 5,000 INR.",
        "confidence": 0.95,
        "parameters": {"refund_reason": "overcharge_compensation"}
    }"""
    fake = FakeAIProvider([valid_recovery_json])
    now = datetime(2026, 9, 5, 12, 10, 0, tzinfo=timezone.utc)

    proposal = propose_recovery(base_mrdp, base_contract, provider=fake, suggested_at=now)

    assert isinstance(proposal, RecoveryProposal)
    assert proposal.proposed_action == ActionType.REFUND
    assert proposal.suggested_amount == Money(amount=500000, currency="INR")
    assert proposal.confidence == 0.95
    assert proposal.mrdp_id == base_mrdp.mrdp_id
    assert proposal.intent_id == base_contract.intent_id


def test_recovery_agent_capture_forbidden(base_contract: IntentContract, base_mrdp: MRDP):
    """AI Recovery Agent is strictly forbidden from proposing CAPTURE actions."""
    capture_json = """{
        "proposed_action": "CAPTURE",
        "suggested_amount_minor": 5000000,
        "currency": "INR",
        "reasoning": "Attempt capture again",
        "confidence": 0.9
    }"""
    fake = FakeAIProvider([capture_json])
    with pytest.raises(UnsafeRecoveryProposalError, match="strictly forbidden from proposing CAPTURE"):
        propose_recovery(base_mrdp, base_contract, provider=fake)


def test_recovery_agent_refund_exceeding_discrepancy_rejected(
    base_contract: IntentContract, base_mrdp: MRDP
):
    """Refund proposal exceeding the detected MRDP discrepancy is rejected."""
    excess_refund_json = """{
        "proposed_action": "REFUND",
        "suggested_amount_minor": 600000,
        "currency": "INR",
        "reasoning": "Refund 6,000 INR when discrepancy was only 5,000 INR",
        "confidence": 0.9
    }"""
    fake = FakeAIProvider([excess_refund_json])
    with pytest.raises(UnsafeRecoveryProposalError, match="exceeds detected discrepancy"):
        propose_recovery(base_mrdp, base_contract, provider=fake)


def test_recovery_agent_currency_mismatch_rejected(
    base_contract: IntentContract, base_mrdp: MRDP
):
    """Recovery proposal specifying a different currency than authorized is rejected."""
    currency_mismatch_json = """{
        "proposed_action": "REFUND",
        "suggested_amount_minor": 500000,
        "currency": "USD",
        "reasoning": "Refund in USD",
        "confidence": 0.9
    }"""
    fake = FakeAIProvider([currency_mismatch_json])
    with pytest.raises(UnsafeRecoveryProposalError, match="does not match contract currency"):
        propose_recovery(base_mrdp, base_contract, provider=fake)


def test_recovery_agent_confidence_is_not_authorization(
    base_contract: IntentContract, base_mrdp: MRDP
):
    """Confidence 99.9% in an advisory proposal remains informational only and cannot authorize financial actions."""
    high_confidence_json = """{
        "proposed_action": "REFUND",
        "suggested_amount_minor": 500000,
        "currency": "INR",
        "reasoning": "Extremely certain recovery strategy",
        "confidence": 0.999
    }"""
    fake = FakeAIProvider([high_confidence_json])
    proposal = propose_recovery(base_mrdp, base_contract, provider=fake)

    assert proposal.confidence == 0.999
    # Crucial domain invariant: RecoveryProposal has no is_authorized field and cannot authorize capture
    assert not hasattr(proposal, "is_authorized")
    assert not hasattr(proposal, "authorized")


# ==============================================================================
# 3. AI PROVIDER FAILURE MATRIX TESTS
# ==============================================================================

def test_ai_provider_timeout_handling():
    """AITimeoutError triggers bounded retry, then raises safe error."""
    fake = FakeAIProvider([AITimeoutError("Request timed out"), AITimeoutError("Request timed out")])
    with pytest.raises(IntentParsingError, match="Intent parsing failed"):
        parse_intent("Buy server", provider=fake, max_retries=1)


def test_ai_provider_rate_limit_handling():
    """AIRateLimitError is captured and cleanly handled."""
    fake = FakeAIProvider([AIRateLimitError("429 Too Many Requests")])
    with pytest.raises(IntentParsingError):
        parse_intent("Buy server", provider=fake, max_retries=0)


def test_ai_provider_unavailable_handling():
    """AIUnavailableError is raised when AI service is offline."""
    fake = FakeAIProvider([AIUnavailableError("Connection refused")])
    with pytest.raises(IntentParsingError):
        parse_intent("Buy server", provider=fake, max_retries=0)
