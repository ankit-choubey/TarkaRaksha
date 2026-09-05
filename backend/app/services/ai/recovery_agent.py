"""
Advisory Recovery Agent Service for TarkaRaksha (T08).
Consumes an MRDP and the original IntentContract to generate an advisory RecoveryProposal.
Applies deterministic safety validation to ensure AI suggestions never attempt budget increases,
verifier bypasses, or unauthorized financial captures.
"""
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Optional
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.domain.models import (
    ActionType,
    IntentContract,
    Money,
    MRDP,
    RecoveryProposal,
)
from .contracts import (
    AIRecoverySuggestion,
    AIProviderError,
    StructuredOutputError,
    UnsafeRecoveryProposalError,
)
from .provider import AIProvider, GroqAIProvider

logger = logging.getLogger(__name__)

RECOVERY_AGENT_SYSTEM_PROMPT = """You are TarkaRaksha's Advisory Recovery Agent.
Your sole job is to analyze a Machine-Readable Drift Proof (MRDP) and original IntentContract
to propose an advisory corrective recovery strategy.

YOU HAVE NO FINANCIAL AUTHORITY.
You cannot authorize money transfers, capture funds, or declare transaction PASS.
Your proposal is strictly advisory and will undergo rigorous deterministic policy validation.

You must respond strictly with valid JSON conforming to the following JSON schema:
{
  "proposed_action": "string (one of: REFUND, VOID, CANCEL, NOTIFY, HOLD)",
  "suggested_amount_minor": "integer or null (amount in minor currency units, e.g. paise. Must be null for VOID/CANCEL/HOLD/NOTIFY or for full cancellation)",
  "currency": "string (3-letter ISO-4217 code matching authorized contract, e.g. INR)",
  "reasoning": "string (concise technical justification for why this recovery remediates the drift)",
  "confidence": "number between 0.0 and 1.0 (self-assessed confidence, strictly informational)",
  "parameters": {"key": "value"}
}

STRICT SAFETY INVARIANTS:
1. NEVER propose CAPTURE. Capture cannot be initiated by an AI recovery agent.
2. NEVER propose increasing the budget, authorizing additional funds, or exceeding the original contract max_total.
3. NEVER attempt to alter the authorized SKU or quantity constraints.
4. NEVER advise bypassing the verifier, ignoring constraints, or forcing a PASS state.
5. If the drift is an economic overcharge, propose a REFUND or VOID for the excess discrepancy amount.
6. If the drift is semantic (wrong SKU/quantity), propose VOID or CANCEL.
7. If the status is UNKNOWN (conflicting evidence), propose HOLD or NOTIFY to request authoritative gateway revalidation.
"""

FORBIDDEN_RECOVERY_PHRASES = [
    "ignore budget",
    "increase budget",
    "increase authorization",
    "bypass verifier",
    "bypass verification",
    "force pass",
    "override drift",
    "ignore constraint",
    "capture without authorization",
    "alter contract",
    "alter authorization",
]


def propose_recovery(
    mrdp: MRDP,
    contract: IntentContract,
    provider: Optional[AIProvider] = None,
    suggested_at: Optional[datetime] = None,
    max_retries: Optional[int] = None,
) -> RecoveryProposal:
    """
    Generates an advisory RecoveryProposal for a given MRDP and IntentContract.
    Undergoes strict deterministic validation. Rejects any proposal attempting to violate safety boundaries.
    """
    if mrdp.intent_id != contract.intent_id:
        raise ValueError(
            f"MRDP intent_id '{mrdp.intent_id}' does not match contract intent_id '{contract.intent_id}'"
        )

    ai_provider = provider or GroqAIProvider()
    retries = max_retries if max_retries is not None else settings.groq_max_retries

    current_suggested_at = suggested_at or datetime.now(timezone.utc)
    if current_suggested_at.tzinfo is None:
        raise ValueError("suggested_at must be timezone-aware (UTC)")

    user_prompt = _build_recovery_agent_prompt(mrdp, contract)
    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            raw_response = ai_provider.generate(
                prompt=user_prompt,
                system_prompt=RECOVERY_AGENT_SYSTEM_PROMPT,
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            # Step 1: JSON Parsing
            try:
                payload = json.loads(raw_response)
            except json.JSONDecodeError as jde:
                raise StructuredOutputError(f"AI recovery response was not valid JSON: {jde}") from jde

            # Step 2: Strict Pydantic DTO Validation
            try:
                suggestion = AIRecoverySuggestion.model_validate(payload)
            except ValidationError as ve:
                raise StructuredOutputError(f"AI recovery suggestion failed schema validation: {ve}") from ve

            # Step 3: Deterministic Safety Validation
            validate_recovery_proposal_safety(suggestion, contract, mrdp)

            # Step 4: Construct Domain RecoveryProposal
            proposal = _convert_suggestion_to_proposal(
                suggestion=suggestion,
                mrdp=mrdp,
                contract=contract,
                suggested_at=current_suggested_at,
                model_name=getattr(ai_provider, "model", "groq-advisory-agent"),
            )
            return proposal

        except (StructuredOutputError, AIProviderError) as exc:
            last_error = exc
            logger.warning("Recovery proposal attempt %d/%d failed: %s", attempt + 1, retries + 1, exc)
            if attempt >= retries:
                break

    raise StructuredOutputError(
        f"Recovery agent proposal failed after {retries + 1} attempts. Last error: {last_error}"
    ) from last_error


def validate_recovery_proposal_safety(
    suggestion: AIRecoverySuggestion,
    contract: IntentContract,
    mrdp: MRDP,
) -> None:
    """
    Deterministic safety validator for AI recovery suggestions.
    Enforces that AI advice can never breach financial, semantic, or authorization bounds.
    """
    # Safety Rule 1: AI cannot propose financial capture
    if suggestion.proposed_action == ActionType.CAPTURE:
        raise UnsafeRecoveryProposalError("AI Recovery Agent is strictly forbidden from proposing CAPTURE actions")

    # Safety Rule 2: Currency alignment
    if suggestion.suggested_amount_minor is not None:
        if suggestion.currency and suggestion.currency.upper() != contract.currency:
            raise UnsafeRecoveryProposalError(
                f"Proposed currency '{suggestion.currency}' does not match contract currency '{contract.currency}'"
            )

        # Safety Rule 3: Suggested amount cannot exceed contract maximum total
        if suggestion.suggested_amount_minor > contract.max_total.amount:
            raise UnsafeRecoveryProposalError(
                f"Proposed amount {suggestion.suggested_amount_minor} minor units exceeds authorized max_total {contract.max_total.amount}"
            )

        # Safety Rule 4: If discrepancy amount exists and action is refund, amount cannot exceed discrepancy
        if suggestion.proposed_action == ActionType.REFUND and mrdp.discrepancy_amount is not None:
            if suggestion.suggested_amount_minor > mrdp.discrepancy_amount.amount:
                raise UnsafeRecoveryProposalError(
                    f"Proposed refund amount {suggestion.suggested_amount_minor} exceeds detected discrepancy {mrdp.discrepancy_amount.amount}"
                )

    # Safety Rule 5: Reasoning must not contain forbidden prompt injection or bypass instructions
    reasoning_lower = suggestion.reasoning.lower()
    for phrase in FORBIDDEN_RECOVERY_PHRASES:
        if phrase in reasoning_lower:
            raise UnsafeRecoveryProposalError(
                f"Recovery reasoning contains forbidden instruction: '{phrase}'"
            )


def _convert_suggestion_to_proposal(
    suggestion: AIRecoverySuggestion,
    mrdp: MRDP,
    contract: IntentContract,
    suggested_at: datetime,
    model_name: Optional[str],
) -> RecoveryProposal:
    """Converts a validated AIRecoverySuggestion into an authoritative domain RecoveryProposal."""
    suggested_money: Optional[Money] = None
    if suggestion.suggested_amount_minor is not None:
        curr = suggestion.currency or contract.currency
        suggested_money = Money(amount=suggestion.suggested_amount_minor, currency=curr)

    # Deterministic proposal ID
    id_input = f"{mrdp.mrdp_id}:{suggestion.proposed_action.value}:{suggested_at.isoformat()}"
    proposal_id = f"prop_{hashlib.sha256(id_input.encode('utf-8')).hexdigest()[:16]}"

    return RecoveryProposal(
        proposal_id=proposal_id,
        mrdp_id=mrdp.mrdp_id,
        intent_id=contract.intent_id,
        proposed_action=suggestion.proposed_action,
        suggested_amount=suggested_money,
        reasoning=suggestion.reasoning,
        confidence=suggestion.confidence,
        suggested_at=suggested_at,
        model_identifier=model_name,
        parameters=suggestion.parameters,
    )


def _build_recovery_agent_prompt(mrdp: MRDP, contract: IntentContract) -> str:
    """Formats the MRDP and Contract context into an inert data prompt for the recovery model."""
    context = {
        "intent_id": contract.intent_id,
        "authorized_sku": contract.items[0].sku if contract.items else "N/A",
        "authorized_quantity": contract.items[0].quantity if contract.items else 0,
        "authorized_max_total": f"{contract.max_total.amount} {contract.max_total.currency}",
        "mrdp_status": mrdp.status.value,
        "mrdp_error_code": mrdp.error_code,
        "mrdp_violation": mrdp.violation,
        "mrdp_drift_source": mrdp.drift_source,
        "mrdp_expected": str(mrdp.expected_value),
        "mrdp_observed": str(mrdp.observed_value),
        "discrepancy": f"{mrdp.discrepancy_amount.amount} {mrdp.discrepancy_amount.currency}" if mrdp.discrepancy_amount else "None",
        "revalidation_required": mrdp.revalidation_required,
    }
    return f"Analyze the following drift proof and propose an advisory corrective recovery action:\n{json.dumps(context, indent=2)}"
