"""Unit tests for I21 EvidenceAwareExplanationService."""
from datetime import datetime, timezone
import json
import pytest

from backend.app.domain.explanation.contracts import (
    EvidenceReference,
    ExplanationContext,
)
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.models.enums import EvidenceAuthority, EvidenceSource, IntegrityStatus
from backend.app.services.ai.contracts import (
    AIRateLimitError,
    AITimeoutError,
    AIUnavailableError,
)
from backend.app.services.ai.provider import FakeAIProvider
from backend.app.services.explanation.service import EvidenceAwareExplanationService


@pytest.fixture
def sample_context():
    now = datetime.now(timezone.utc)
    ev_amt = EvidenceReference(
        evidence_id="ev_amt_test",
        field_name="amount",
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        observed_value=25000,
        expected_value=25000,
        is_authoritative=True,
    )
    return ExplanationContext(
        context_id="ctx_srv_1",
        transaction_id="tx_srv_1",
        intent_id="intent_srv_1",
        deterministic_decision=IntegrityStatus.PASS,
        decision_reason="All constraints met",
        kill_switch_state=KillSwitchState.RUNNING,
        evidence_references=[ev_amt],
        created_at=now,
    )


def test_service_happy_path_with_valid_ai_response(sample_context):
    valid_ai_payload = {
        "summary": "Transaction verified cleanly against authorized constraints.",
        "deterministic_decision": "PASS",
        "execution_state": "RUNNING",
        "claims": [
            {
                "claim_id": "c1",
                "claim_text": "Payment amount of 25000 paise strictly matched authorized budget.",
                "evidence_refs": ["ev_amt_test"],
                "authority_tier": "AUTHORITATIVE",
                "claim_type": "FACT",
                "category": "ECONOMIC",
            }
        ],
        "mismatches": [],
        "missing_evidence": [],
        "uncertainties": [],
        "recommended_next_action": "Proceed with payment settlement",
    }
    fake_provider = FakeAIProvider(responses=[json.dumps(valid_ai_payload)])
    service = EvidenceAwareExplanationService(ai_provider=fake_provider)

    result = service.explain(sample_context)
    assert result.is_fallback is False
    assert result.deterministic_decision == IntegrityStatus.PASS
    assert result.validation_result.is_valid is True
    assert len(result.claims) == 1
    assert result.claims[0].evidence_refs == ["ev_amt_test"]
    assert fake_provider.call_count == 1


def test_service_falls_back_on_malformed_json(sample_context):
    fake_provider = FakeAIProvider(responses=["NOT A VALID JSON {{{"])
    service = EvidenceAwareExplanationService(ai_provider=fake_provider)

    result = service.explain(sample_context)
    assert result.is_fallback is True
    assert result.deterministic_decision == IntegrityStatus.PASS
    assert "deterministic_fallback" in result.model_metadata["engine"]
    assert "JSONDecodeError" in result.model_metadata["reason"] or "Malformed JSON" in result.model_metadata["reason"]


def test_service_falls_back_on_timeout(sample_context):
    fake_provider = FakeAIProvider(responses=[AITimeoutError("Groq request timed out after 10s")])
    service = EvidenceAwareExplanationService(ai_provider=fake_provider)

    result = service.explain(sample_context)
    assert result.is_fallback is True
    assert "AITimeoutError" in result.model_metadata["reason"]


def test_service_falls_back_on_rate_limit(sample_context):
    fake_provider = FakeAIProvider(responses=[AIRateLimitError("Rate limit 429 exceeded")])
    service = EvidenceAwareExplanationService(ai_provider=fake_provider)

    result = service.explain(sample_context)
    assert result.is_fallback is True
    assert "AIRateLimitError" in result.model_metadata["reason"]


def test_service_falls_back_on_ai_unavailable(sample_context):
    fake_provider = FakeAIProvider(responses=[AIUnavailableError("Groq endpoint 503 unavailable")])
    service = EvidenceAwareExplanationService(ai_provider=fake_provider)

    result = service.explain(sample_context)
    assert result.is_fallback is True
    assert "AIUnavailableError" in result.model_metadata["reason"]


def test_service_falls_back_when_ai_hallucinates_evidence(sample_context):
    hallucinated_ai_payload = {
        "summary": "Transaction verified cleanly.",
        "deterministic_decision": "PASS",
        "execution_state": "RUNNING",
        "claims": [
            {
                "claim_id": "c1",
                "claim_text": "Fictitious authorization cited.",
                "evidence_refs": ["ev_non_existent_999"],  # Hallucinated ID
            }
        ],
    }
    fake_provider = FakeAIProvider(responses=[json.dumps(hallucinated_ai_payload)])
    service = EvidenceAwareExplanationService(ai_provider=fake_provider)

    result = service.explain(sample_context)
    # Validation rejected -> deterministic fallback engaged
    assert result.is_fallback is True
    assert "validation rejected" in result.model_metadata["reason"]
    assert "Hallucinated evidence reference" in result.model_metadata["reason"]
