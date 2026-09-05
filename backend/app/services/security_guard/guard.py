"""TarkaRaksha E4 — Security Guard Service.

Composes the deterministic SecurityThreatEvaluator with repository services
(I9 ExecutionKillSwitchService, I8 AgentTransactionBindingService,
I14 IntegrityCheckpointService) without modifying or breaking any existing service.

Governing Invariant:
AI proposes. Evidence proves. Deterministic logic decides.
E4 does not mutate intent or initiate transactions; it detects,
classifies, references evidence, and triggers safety controls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from backend.app.domain.security_guard.contracts import (
    SecurityGuardContext,
    SecurityGuardResult,
    SecurityStatus,
    SecurityThreatCode,
)
from backend.app.domain.security_guard.evaluator import SecurityThreatEvaluator
from backend.app.domain.negotiation.contracts import NegotiationSession
from backend.app.domain.kill_switch.contracts import KillSwitchState, KillTrigger
from backend.app.services.kill_switch.service import KillSwitchService


class SecurityGuardService:
    """Service boundary for E4 Security / Threat Guard composition."""

    def __init__(
        self,
        kill_switch_service: Optional[KillSwitchService] = None,
    ) -> None:
        self.kill_switch_service = kill_switch_service or KillSwitchService()

    def evaluate(self, ctx: SecurityGuardContext) -> SecurityGuardResult:
        """Run deterministic threat evaluation on context.

        If a critical security violation or blocking threat triggers the kill switch,
        activate the existing I9 KillSwitchService safely.
        """
        result = SecurityThreatEvaluator.evaluate(ctx)

        # Compose with existing I9 kill switch if triggered
        if result.kill_switch_triggered and self.kill_switch_service is not None:
            current_state = self.kill_switch_service.get_state(ctx.transaction_id)
            if current_state == KillSwitchState.RUNNING:
                # Map threat code to KillTrigger
                threat_codes = [f.threat_code for f in result.findings]
                if SecurityThreatCode.AGENT_CAPABILITY_VIOLATION in threat_codes:
                    trigger = KillTrigger.CAPABILITY_VIOLATION
                elif SecurityThreatCode.AUTHORIZATION_EXPIRED in threat_codes:
                    trigger = KillTrigger.EXPIRED_AUTHORIZATION
                elif any(tc in threat_codes for tc in (SecurityThreatCode.AGENT_ID_MISMATCH, SecurityThreatCode.INTENT_MISMATCH, SecurityThreatCode.TRANSACTION_MISMATCH)):
                    trigger = KillTrigger.BINDING_VIOLATION
                else:
                    trigger = KillTrigger.CRITICAL_DRIFT

                self.kill_switch_service.kill(
                    transaction_id=ctx.transaction_id,
                    trigger=trigger,
                    reason=result.kill_switch_reason or "E4 Security Guard Violation",
                    actor="SECURITY_GUARD_E4",
                    details={
                        "threat_codes": [f.threat_code.value for f in result.findings],
                        "reproducibility_hash": result.reproducibility_hash,
                        "evidence_refs": result.evidence_refs,
                    },
                )

        return result

    def evaluate_session(
        self,
        session: NegotiationSession,
        authorized_max_total: Optional[int] = None,
        authorized_currency: str = "INR",
        authorization_expires_at: Optional[datetime] = None,
        proposed_amount: Optional[int] = None,
        untrusted_text: Optional[str] = None,
        current_time: Optional[datetime] = None,
        attempt_id: Optional[str] = None,
        consumed_attempts: Optional[List[str]] = None,
        known_messages: Optional[List[str]] = None,
    ) -> SecurityGuardResult:
        """Helper to construct context directly from a NegotiationSession."""
        untrusted_payloads: List[str] = []
        if untrusted_text:
            untrusted_payloads.append(untrusted_text)

        # Check last round proposal notes/items if present
        if session.rounds:
            last_round = session.rounds[-1]
            if last_round.proposal and hasattr(last_round.proposal, "items"):
                for itm in last_round.proposal.items:
                    if hasattr(itm, "description") and itm.description:
                        untrusted_payloads.append(itm.description)

        ctx = SecurityGuardContext(
            transaction_id=session.transaction_id,
            intent_id=session.intent_id,
            agent_id=session.buyer_agent_id,
            session_id=session.session_id,
            buyer_agent_id=session.buyer_agent_id,
            merchant_agent_id=session.merchant_id,
            authorized_max_total=authorized_max_total,
            authorized_currency=authorized_currency,
            authorization_expires_at=authorization_expires_at,
            current_time=current_time or datetime.now(timezone.utc),
            proposed_amount=proposed_amount,
            untrusted_payloads=untrusted_payloads,
            attempt_id=attempt_id,
            consumed_attempt_ids=consumed_attempts or [],
            known_message_ids=known_messages or [],
            metadata={
                "session_state": session.state.value if hasattr(session.state, "value") else str(session.state),
            },
        )

        return self.evaluate(ctx)

    def evaluate_integration_context(self, integration_ctx: Any) -> SecurityGuardResult:
        """Integration hook for E1/E-series contexts.

        Accepts any object conforming to integration context protocol
        without importing or coupling directly to unverified E1 paths.
        """
        # Safely extract attributes if present
        tx_id = getattr(integration_ctx, "transaction_id", getattr(integration_ctx, "tx_id", "unknown_tx"))
        intent_id = getattr(integration_ctx, "intent_id", "unknown_intent")
        agent_id = getattr(integration_ctx, "agent_id", "unknown_agent")

        ctx = SecurityGuardContext(
            transaction_id=tx_id,
            intent_id=intent_id,
            agent_id=agent_id,
            buyer_agent_id=getattr(integration_ctx, "buyer_agent_id", None),
            merchant_agent_id=getattr(integration_ctx, "merchant_agent_id", None),
            authorized_max_total=getattr(integration_ctx, "authorized_max_total", None),
            proposed_amount=getattr(integration_ctx, "proposed_amount", None),
            untrusted_payloads=getattr(integration_ctx, "untrusted_payloads", []),
            metadata=getattr(integration_ctx, "metadata", {}),
        )
        return self.evaluate(ctx)
