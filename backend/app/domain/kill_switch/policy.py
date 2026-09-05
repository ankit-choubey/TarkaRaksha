"""Pure deterministic policy and transition rules for I9 Kill Switch.

Enforces execution-control transition table, trigger mappings, and authoritative
evaluation logic without live network calls, external clock randomness, or LLM involvement.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from backend.app.domain.binding.contracts import BindingVerificationOutcome
from backend.app.domain.kill_switch.contracts import (
    ExecutionDecision,
    KillSwitchState,
    KillTrigger,
    RevalidationOutcome,
    RevalidationRequest,
    UnauthorizedResumeError,
)
from backend.app.domain.models.enums import EvidenceAuthority, IntegrityStatus
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.integrity import IntegrityResult


# Permitted transition graph for execution-control states
PERMITTED_SAFETY_TRANSITIONS: Dict[KillSwitchState, Set[KillSwitchState]] = {
    # 1. RUNNING: Normal execution permitted
    KillSwitchState.RUNNING: {
        KillSwitchState.PAUSED,
        KillSwitchState.REQUIRES_REVALIDATION,
        KillSwitchState.KILLED,
    },
    # 2. PAUSED: Held temporarily; can be unpaused or escalated
    KillSwitchState.PAUSED: {
        KillSwitchState.RUNNING,
        KillSwitchState.REQUIRES_REVALIDATION,
        KillSwitchState.KILLED,
    },
    # 3. REQUIRES_REVALIDATION: Blocked; can only move to RUNNING upon verified revalidation, or KILLED
    KillSwitchState.REQUIRES_REVALIDATION: {
        KillSwitchState.RUNNING,
        KillSwitchState.KILLED,
    },
    # 4. KILLED: Execution halted; CANNOT transition directly to RUNNING. Must enter REQUIRES_REVALIDATION first
    KillSwitchState.KILLED: {
        KillSwitchState.REQUIRES_REVALIDATION,
    },
}


class KillSwitchPolicy:
    """Pure deterministic policy logic for execution safety control."""

    @classmethod
    def can_transition(cls, from_state: KillSwitchState, to_state: KillSwitchState) -> bool:
        """Check whether transition from from_state to to_state is structurally legal."""
        return to_state in PERMITTED_SAFETY_TRANSITIONS.get(from_state, set())

    @classmethod
    def validate_transition(
        cls,
        from_state: KillSwitchState,
        to_state: KillSwitchState,
        trigger: Optional[KillTrigger] = None,
    ) -> None:
        """
        Validate safety state transition against the authoritative transition table.
        Raises UnauthorizedResumeError or ValueError if illegal.
        """
        if from_state == to_state:
            return  # Idempotent no-op

        if from_state == KillSwitchState.KILLED and to_state == KillSwitchState.RUNNING:
            raise UnauthorizedResumeError(
                "Direct transition from KILLED to RUNNING is strictly forbidden. "
                "A killed transaction must undergo authoritative revalidation first."
            )

        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                f"Illegal safety state transition from '{from_state.value}' to '{to_state.value}' "
                f"under trigger '{trigger.value if trigger else 'None'}'."
            )

    @classmethod
    def evaluate_integrity_findings(
        cls,
        integrity_result: IntegrityResult,
        unknown_attempts: int = 0,
        max_unknown_tolerance: int = 2,
    ) -> Optional[tuple[KillSwitchState, ExecutionDecision, KillTrigger, str]]:
        """
        Evaluate findings from deterministic integrity evaluation (T04).
        Returns None if safe (PASS), or (new_state, decision, trigger, reason) if intervention required.
        """
        if integrity_result.status == IntegrityStatus.DRIFT:
            violations_summary = ", ".join(integrity_result.violations) if integrity_result.violations else "Integrity drift detected"
            return (
                KillSwitchState.KILLED,
                ExecutionDecision.BLOCK,
                KillTrigger.CRITICAL_DRIFT,
                f"Critical integrity drift: {violations_summary}",
            )

        if integrity_result.status == IntegrityStatus.UNKNOWN:
            if unknown_attempts >= max_unknown_tolerance:
                return (
                    KillSwitchState.REQUIRES_REVALIDATION,
                    ExecutionDecision.REQUIRE_REVALIDATION,
                    KillTrigger.REPEATED_UNKNOWN,
                    f"Repeated unresolved UNKNOWN state ({unknown_attempts} attempts >= tolerance {max_unknown_tolerance}). "
                    f"Execution halted to prevent unverified financial risk.",
                )

        return None

    @classmethod
    def evaluate_binding_outcome(
        cls,
        binding_outcome: BindingVerificationOutcome,
    ) -> Optional[tuple[KillSwitchState, ExecutionDecision, KillTrigger, str]]:
        """
        Evaluate authoritative findings from I8 TransactionBindingVerifier.
        Returns None if valid, or (new_state, decision, trigger, reason) if binding failed.
        """
        if not binding_outcome.is_valid:
            violations = ", ".join(v.value for v in binding_outcome.violations) if binding_outcome.violations else "Context binding mismatch"
            return (
                KillSwitchState.KILLED,
                ExecutionDecision.BLOCK,
                KillTrigger.BINDING_VIOLATION,
                f"Binding violation detected: {violations}. {binding_outcome.explanation}",
            )
        return None

    @classmethod
    def evaluate_intent_freshness(
        cls,
        intent: IntentContract,
        reference_time: datetime,
    ) -> Optional[tuple[KillSwitchState, ExecutionDecision, KillTrigger, str]]:
        """
        Evaluate if IntentContract authorization has expired relative to explicit reference time.
        """
        ref_time = reference_time
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        if ref_time > intent.expires_at:
            return (
                KillSwitchState.REQUIRES_REVALIDATION,
                ExecutionDecision.REQUIRE_REVALIDATION,
                KillTrigger.EXPIRED_AUTHORIZATION,
                f"Intent authorization expired at {intent.expires_at.isoformat()} (ref: {ref_time.isoformat()}). "
                f"Revalidation required before continuing.",
            )
        return None

    @classmethod
    def evaluate_revalidation(
        cls,
        request: RevalidationRequest,
        expected_transaction_id: str,
        expected_intent_id: str,
        expected_agent_id: str,
        expected_merchant_id: str,
        reference_time: datetime,
    ) -> RevalidationOutcome:
        """
        Deterministically evaluates a RevalidationRequest.
        Enforces strict context matching, non-empty authoritative evidence, and freshness.
        """
        ref_time = reference_time
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        violations: List[str] = []

        # 1. Context matching
        if request.transaction_id != expected_transaction_id:
            violations.append(f"Mismatched transaction_id: claimed '{request.transaction_id}' != expected '{expected_transaction_id}'")
        if request.intent_id != expected_intent_id:
            violations.append(f"Mismatched intent_id: claimed '{request.intent_id}' != expected '{expected_intent_id}'")
        if request.agent_id != expected_agent_id:
            violations.append(f"Mismatched agent_id: claimed '{request.agent_id}' != expected '{expected_agent_id}'")
        if request.merchant_id != expected_merchant_id:
            violations.append(f"Mismatched merchant_id: claimed '{request.merchant_id}' != expected '{expected_merchant_id}'")

        # 2. Evidence sufficiency: Must provide at least one authoritative or protocol-trusted evidence record
        if not request.evidence:
            violations.append("Revalidation requires at least one authoritative evidence item; none provided")
        else:
            has_authoritative = any(
                ev.effective_authority in (EvidenceAuthority.AUTHORITATIVE, EvidenceAuthority.PROTOCOL_TRUSTED)
                for ev in request.evidence
            )
            if not has_authoritative:
                violations.append("Revalidation evidence must include at least one AUTHORITATIVE or PROTOCOL_TRUSTED record")

        # 3. Freshness check: Request cannot be future-dated beyond 60s or older than 24h
        time_diff = (ref_time - request.requested_at).total_seconds()
        if time_diff < -60.0:
            violations.append(f"Revalidation request is future-dated by {-time_diff:.1f}s")
        elif time_diff > 86400.0:
            violations.append(f"Revalidation request is stale ({time_diff / 3600:.1f} hours old)")

        if violations:
            return RevalidationOutcome(
                is_valid=False,
                decision=ExecutionDecision.BLOCK,
                explanation="Revalidation failed: " + "; ".join(violations),
                evaluated_at=ref_time,
                violations=violations,
            )

        return RevalidationOutcome(
            is_valid=True,
            decision=ExecutionDecision.ALLOW,
            explanation="Authoritative revalidation satisfied; execution resumption permitted.",
            evaluated_at=ref_time,
            violations=[],
        )
