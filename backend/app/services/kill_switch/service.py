"""Service orchestrator for I9 Deterministic Kill Switch / Execution Safety Control.

Maintains active execution safety state for protected transactions, enforces
fail-safe execution blocking, and manages authenticated revalidation lifecycles.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from backend.app.domain.binding.contracts import BindingVerificationOutcome
from backend.app.domain.kill_switch.contracts import (
    ExecutionBlockedError,
    ExecutionDecision,
    KillSwitchRecord,
    KillSwitchState,
    KillTrigger,
    RevalidationOutcome,
    RevalidationRequest,
    UnauthorizedResumeError,
)
from backend.app.domain.kill_switch.policy import KillSwitchPolicy
from backend.app.domain.models.enums import EvidenceAuthority, IntegrityStatus
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.integrity import IntegrityResult

logger = logging.getLogger(__name__)


class KillSwitchService:
    """
    Control plane service managing deterministic execution safety gates.
    Tracks execution-control states, maintains immutable transition history,
    and enforces fail-closed execution boundaries.
    """

    def __init__(self, max_unknown_tolerance: int = 2):
        self._max_unknown_tolerance = max_unknown_tolerance
        self._states: Dict[str, KillSwitchState] = {}
        self._histories: Dict[str, List[KillSwitchRecord]] = {}
        self._contexts: Dict[str, Dict[str, str]] = {}
        self._unknown_counts: Dict[str, int] = {}

    def register_transaction(
        self,
        transaction_id: str,
        intent_id: str,
        agent_id: str = "user_default",
        merchant_id: str = "merchant_default",
        initial_state: KillSwitchState = KillSwitchState.RUNNING,
        created_at: Optional[datetime] = None,
    ) -> KillSwitchRecord:
        """
        Register a new transaction under execution safety control.
        Initial state is RUNNING unless overridden.
        """
        ts = created_at or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        self._states[transaction_id] = initial_state
        self._contexts[transaction_id] = {
            "intent_id": intent_id,
            "agent_id": agent_id,
            "merchant_id": merchant_id,
        }
        self._unknown_counts[transaction_id] = 0

        initial_record = KillSwitchRecord(
            record_id=f"ks_rec_{transaction_id}_init",
            transaction_id=transaction_id,
            prior_state=initial_state,
            resulting_state=initial_state,
            decision=ExecutionDecision.ALLOW if initial_state == KillSwitchState.RUNNING else ExecutionDecision.BLOCK,
            trigger=None,
            reason="Transaction initialized under execution safety control",
            triggered_by="CONTROL_PLANE",
            authority=EvidenceAuthority.SYSTEM_DERIVED,
            timestamp=ts,
            details={"intent_id": intent_id, "agent_id": agent_id, "merchant_id": merchant_id},
        )
        self._histories[transaction_id] = [initial_record]
        return initial_record

    def get_state(self, transaction_id: str) -> KillSwitchState:
        """Retrieve current execution safety state for a transaction (defaults to KILLED if unknown)."""
        return self._states.get(transaction_id, KillSwitchState.KILLED)

    def get_history(self, transaction_id: str) -> List[KillSwitchRecord]:
        """Retrieve audit history of safety state transitions."""
        return list(self._histories.get(transaction_id, []))

    def get_context(self, transaction_id: str) -> Optional[Dict[str, str]]:
        """Retrieve registered context identifiers for a transaction."""
        return self._contexts.get(transaction_id)

    def assert_can_execute(self, transaction_id: str, operation_name: str = "execute") -> None:
        """
        Fail-safe execution gate: verifies that transaction is in RUNNING state.
        Raises ExecutionBlockedError if transaction is PAUSED, REQUIRES_REVALIDATION, or KILLED.
        """
        state = self.get_state(transaction_id)
        if state != KillSwitchState.RUNNING:
            history = self.get_history(transaction_id)
            last_record = history[-1] if history else None
            trigger = last_record.trigger if last_record else None
            reason = last_record.reason if last_record else "Execution blocked by safety control"
            raise ExecutionBlockedError(
                f"Execution blocked for transaction '{transaction_id}' in state '{state.value}' "
                f"during operation '{operation_name}': {reason}",
                state=state,
                trigger=trigger,
            )

    def kill(
        self,
        transaction_id: str,
        trigger: KillTrigger = KillTrigger.ADMINISTRATIVE_KILL,
        reason: str = "Administrative execution kill",
        actor: str = "CONTROL_PLANE",
        timestamp: Optional[datetime] = None,
        authority: EvidenceAuthority = EvidenceAuthority.AUTHORITATIVE,
        details: Optional[Dict[str, Any]] = None,
    ) -> KillSwitchRecord:
        """
        Deterministically halts execution by transitioning to KILLED state.
        Idempotent: repeated calls with matching trigger preserve history without corruption.
        """
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        current_state = self.get_state(transaction_id)

        # Idempotency check: if already killed with same reason and trigger
        history = self._histories.get(transaction_id, [])
        if current_state == KillSwitchState.KILLED and history:
            last = history[-1]
            if last.trigger == trigger and last.reason == reason:
                return last

        # Validate transition
        KillSwitchPolicy.validate_transition(current_state, KillSwitchState.KILLED, trigger=trigger)

        record_id = f"ks_rec_{transaction_id}_{ts.strftime('%Y%m%d%H%M%S%f')}"
        record = KillSwitchRecord(
            record_id=record_id,
            transaction_id=transaction_id,
            prior_state=current_state,
            resulting_state=KillSwitchState.KILLED,
            decision=ExecutionDecision.BLOCK,
            trigger=trigger,
            reason=reason,
            triggered_by=actor,
            authority=authority,
            timestamp=ts,
            details=details or {},
            revalidation_requirements=["AUTHORITATIVE_CONTEXT_VERIFICATION", "ADMINISTRATIVE_REVALIDATION"],
        )

        self._states[transaction_id] = KillSwitchState.KILLED
        if transaction_id not in self._histories:
            self._histories[transaction_id] = []
        self._histories[transaction_id].append(record)

        logger.warning(
            f"Kill switch activated for transaction {transaction_id}: "
            f"trigger={trigger.value}, reason={reason}, actor={actor}"
        )
        return record

    def pause(
        self,
        transaction_id: str,
        reason: str = "Administrative pause",
        actor: str = "CONTROL_PLANE",
        timestamp: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> KillSwitchRecord:
        """Temporarily pauses execution for observation or operational hold."""
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        current_state = self.get_state(transaction_id)
        if current_state == KillSwitchState.PAUSED:
            return self._histories[transaction_id][-1]

        KillSwitchPolicy.validate_transition(current_state, KillSwitchState.PAUSED, trigger=KillTrigger.ADMINISTRATIVE_PAUSE)

        record = KillSwitchRecord(
            record_id=f"ks_rec_{transaction_id}_{ts.strftime('%Y%m%d%H%M%S%f')}",
            transaction_id=transaction_id,
            prior_state=current_state,
            resulting_state=KillSwitchState.PAUSED,
            decision=ExecutionDecision.BLOCK,
            trigger=KillTrigger.ADMINISTRATIVE_PAUSE,
            reason=reason,
            triggered_by=actor,
            authority=EvidenceAuthority.SYSTEM_DERIVED,
            timestamp=ts,
            details=details or {},
        )
        self._states[transaction_id] = KillSwitchState.PAUSED
        self._histories[transaction_id].append(record)
        return record

    def unpause(
        self,
        transaction_id: str,
        reason: str = "Administrative unpause",
        actor: str = "CONTROL_PLANE",
        timestamp: Optional[datetime] = None,
    ) -> KillSwitchRecord:
        """Restores a PAUSED transaction to RUNNING."""
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        current_state = self.get_state(transaction_id)
        if current_state != KillSwitchState.PAUSED:
            raise ValueError(f"Cannot unpause transaction '{transaction_id}' in state '{current_state.value}'")

        KillSwitchPolicy.validate_transition(current_state, KillSwitchState.RUNNING)

        record = KillSwitchRecord(
            record_id=f"ks_rec_{transaction_id}_{ts.strftime('%Y%m%d%H%M%S%f')}",
            transaction_id=transaction_id,
            prior_state=current_state,
            resulting_state=KillSwitchState.RUNNING,
            decision=ExecutionDecision.ALLOW,
            trigger=None,
            reason=reason,
            triggered_by=actor,
            authority=EvidenceAuthority.SYSTEM_DERIVED,
            timestamp=ts,
        )
        self._states[transaction_id] = KillSwitchState.RUNNING
        self._histories[transaction_id].append(record)
        return record

    def initiate_revalidation(
        self,
        transaction_id: str,
        reason: str,
        actor: str = "CONTROL_PLANE",
        timestamp: Optional[datetime] = None,
        trigger: Optional[KillTrigger] = None,
    ) -> KillSwitchRecord:
        """Transitions KILLED or PAUSED transaction into REQUIRES_REVALIDATION pathway."""
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        current_state = self.get_state(transaction_id)
        KillSwitchPolicy.validate_transition(current_state, KillSwitchState.REQUIRES_REVALIDATION, trigger=trigger)

        record = KillSwitchRecord(
            record_id=f"ks_rec_{transaction_id}_{ts.strftime('%Y%m%d%H%M%S%f')}",
            transaction_id=transaction_id,
            prior_state=current_state,
            resulting_state=KillSwitchState.REQUIRES_REVALIDATION,
            decision=ExecutionDecision.REQUIRE_REVALIDATION,
            trigger=trigger,
            reason=reason,
            triggered_by=actor,
            authority=EvidenceAuthority.SYSTEM_DERIVED,
            timestamp=ts,
            revalidation_requirements=["CONTEXT_MATCHING", "AUTHORITATIVE_EVIDENCE"],
        )
        self._states[transaction_id] = KillSwitchState.REQUIRES_REVALIDATION
        if transaction_id not in self._histories:
            self._histories[transaction_id] = []
        self._histories[transaction_id].append(record)
        return record

    def revalidate(
        self,
        transaction_id: str,
        request: RevalidationRequest,
        reference_time: Optional[datetime] = None,
    ) -> RevalidationOutcome:
        """
        Processes an authenticated RevalidationRequest.
        If valid: transitions REQUIRES_REVALIDATION -> RUNNING.
        If invalid: remains in blocked state and records audit failure.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        current_state = self.get_state(transaction_id)
        context = self.get_context(transaction_id)
        if not context:
            raise KeyError(f"Transaction '{transaction_id}' has no registered safety context")

        # Evaluate revalidation claim against registered context
        outcome = KillSwitchPolicy.evaluate_revalidation(
            request=request,
            expected_transaction_id=transaction_id,
            expected_intent_id=context["intent_id"],
            expected_agent_id=context["agent_id"],
            expected_merchant_id=context["merchant_id"],
            reference_time=ref_time,
        )

        if outcome.is_valid:
            # Must transition from REQUIRES_REVALIDATION to RUNNING
            # If current state was KILLED, initiate_revalidation first
            if current_state == KillSwitchState.KILLED:
                self.initiate_revalidation(
                    transaction_id=transaction_id,
                    reason="Administrative revalidation workflow initiated",
                    actor=request.actor,
                    timestamp=ref_time,
                )
                current_state = KillSwitchState.REQUIRES_REVALIDATION

            KillSwitchPolicy.validate_transition(current_state, KillSwitchState.RUNNING)

            record = KillSwitchRecord(
                record_id=f"ks_rec_{transaction_id}_{ref_time.strftime('%Y%m%d%H%M%S%f')}",
                transaction_id=transaction_id,
                prior_state=current_state,
                resulting_state=KillSwitchState.RUNNING,
                decision=ExecutionDecision.ALLOW,
                trigger=None,
                reason=f"Revalidation successful: {outcome.explanation}",
                triggered_by=request.actor,
                authority=EvidenceAuthority.AUTHORITATIVE,
                timestamp=ref_time,
                details={"request_id": request.request_id},
            )
            self._states[transaction_id] = KillSwitchState.RUNNING
            self._histories[transaction_id].append(record)
            self._unknown_counts[transaction_id] = 0
            logger.info(f"Transaction {transaction_id} revalidated and resumed by {request.actor}")
        else:
            # Revalidation failed: record in history, stay blocked
            record = KillSwitchRecord(
                record_id=f"ks_rec_{transaction_id}_{ref_time.strftime('%Y%m%d%H%M%S%f')}",
                transaction_id=transaction_id,
                prior_state=current_state,
                resulting_state=current_state,
                decision=ExecutionDecision.BLOCK,
                trigger=None,
                reason=f"Revalidation attempt rejected: {outcome.explanation}",
                triggered_by=request.actor,
                authority=EvidenceAuthority.SYSTEM_DERIVED,
                timestamp=ref_time,
                details={"violations": outcome.violations},
            )
            self._histories[transaction_id].append(record)
            logger.warning(f"Revalidation rejected for {transaction_id}: {outcome.explanation}")

        return outcome

    def evaluate_and_enforce(
        self,
        transaction_id: str,
        intent: IntentContract,
        integrity_result: Optional[IntegrityResult] = None,
        binding_outcome: Optional[BindingVerificationOutcome] = None,
        reference_time: Optional[datetime] = None,
    ) -> Optional[KillSwitchRecord]:
        """
        Evaluates authoritative observations and findings from T04 and I8.
        If a safety violation is present, enforces the kill switch and halts execution.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        # 1. Intent Freshness
        expiry_finding = KillSwitchPolicy.evaluate_intent_freshness(intent, ref_time)
        if expiry_finding:
            new_state, _, trigger, reason = expiry_finding
            return self.initiate_revalidation(
                transaction_id=transaction_id,
                reason=reason,
                actor="SYSTEM",
                timestamp=ref_time,
                trigger=trigger,
            )

        # 2. I8 Binding Findings
        if binding_outcome is not None:
            binding_finding = KillSwitchPolicy.evaluate_binding_outcome(binding_outcome)
            if binding_finding:
                _, _, trigger, reason = binding_finding
                return self.kill(
                    transaction_id=transaction_id,
                    trigger=trigger,
                    reason=reason,
                    actor="TransactionBindingVerifier",
                    timestamp=ref_time,
                    authority=EvidenceAuthority.AUTHORITATIVE,
                )

        # 3. T04 Integrity Findings
        if integrity_result is not None:
            if integrity_result.status == IntegrityStatus.UNKNOWN:
                self._unknown_counts[transaction_id] = self._unknown_counts.get(transaction_id, 0) + 1

            integrity_finding = KillSwitchPolicy.evaluate_integrity_findings(
                integrity_result=integrity_result,
                unknown_attempts=self._unknown_counts.get(transaction_id, 0),
                max_unknown_tolerance=self._max_unknown_tolerance,
            )
            if integrity_finding:
                new_state, _, trigger, reason = integrity_finding
                if new_state == KillSwitchState.KILLED:
                    return self.kill(
                        transaction_id=transaction_id,
                        trigger=trigger,
                        reason=reason,
                        actor="DeterministicIntegrityEngine",
                        timestamp=ref_time,
                        authority=EvidenceAuthority.AUTHORITATIVE,
                    )
                elif new_state == KillSwitchState.REQUIRES_REVALIDATION:
                    return self.initiate_revalidation(
                        transaction_id=transaction_id,
                        reason=reason,
                        actor="UnknownObserver",
                        timestamp=ref_time,
                        trigger=trigger,
                    )

        return None
