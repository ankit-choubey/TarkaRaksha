"""Integrity Checkpoint Service for Innovation I14 — Integrity Checkpoints.

Orchestrates deterministic integrity checkpoint construction, hash chain verification,
and boundary timeline inspection from active runtime sessions or historical records.
Completely deterministic and read-only.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.app.domain.checkpoint.contracts import (
    IntegrityCheckpoint,
    IntegrityCheckpointTimeline,
    ChainVerificationResult,
    verify_checkpoint_chain,
)
from backend.app.domain.checkpoint.engine import DeterministicCheckpointEngine
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.evidence import CanonicalEvent, Evidence, EvidenceBundle
from backend.app.domain.models.integrity import IntegrityResult, MRDP
from backend.app.domain.binding.contracts import BindingContext, BindingVerificationOutcome
from backend.app.domain.kill_switch.contracts import KillSwitchRecord, KillSwitchState
from backend.app.domain.trace.contracts import IntegrityTrace
from backend.app.services.trace.service import IntegrityTraceService


class IntegrityCheckpointService:
    """
    Service layer coordinator for generating and verifying deterministic IntegrityCheckpointTimelines.
    Used by TransactionService, Replay audit, Explanation layer, and API endpoints.
    """

    def __init__(
        self,
        engine: Optional[DeterministicCheckpointEngine] = None,
        trace_service: Optional[IntegrityTraceService] = None,
    ):
        self._engine = engine or DeterministicCheckpointEngine
        self._trace_service = trace_service or IntegrityTraceService()

    def build_timeline(
        self,
        transaction_id: str,
        intent: Optional[IntentContract] = None,
        order: Optional[ProviderOrder] = None,
        payment: Optional[ProviderPayment] = None,
        binding_context: Optional[BindingContext] = None,
        integrity_result: Optional[IntegrityResult] = None,
        binding_outcome: Optional[BindingVerificationOutcome] = None,
        kill_switch_state: KillSwitchState = KillSwitchState.RUNNING,
        kill_switch_record: Optional[KillSwitchRecord] = None,
        evidence_bundle: Optional[EvidenceBundle] = None,
        evidence_list: Optional[List[Evidence]] = None,
        events: Optional[List[CanonicalEvent]] = None,
        mrdp: Optional[MRDP] = None,
        state_machine_state: Optional[str] = None,
        integrity_trace: Optional[IntegrityTrace] = None,
        governance_version: str = "gov_v1.0.0",
        reproducibility_reference: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> IntegrityCheckpointTimeline:
        """Constructs an IntegrityCheckpointTimeline deterministically from provided parameters."""
        return self._engine.generate_timeline(
            transaction_id=transaction_id,
            intent=intent,
            order=order,
            payment=payment,
            binding_context=binding_context,
            integrity_result=integrity_result,
            binding_outcome=binding_outcome,
            kill_switch_state=kill_switch_state,
            kill_switch_record=kill_switch_record,
            evidence_bundle=evidence_bundle,
            evidence_list=evidence_list,
            events=events,
            mrdp=mrdp,
            state_machine_state=state_machine_state,
            integrity_trace=integrity_trace,
            governance_version=governance_version,
            reproducibility_reference=reproducibility_reference,
            reference_time=reference_time,
        )

    def build_timeline_from_session(
        self,
        session: Any,
        kill_switch_state: KillSwitchState = KillSwitchState.RUNNING,
        reference_time: Optional[datetime] = None,
    ) -> IntegrityCheckpointTimeline:
        """Constructs an IntegrityCheckpointTimeline from a TransactionSession object."""
        mrdp = None
        if hasattr(session, "completed_response") and session.completed_response:
            mrdp = getattr(session.completed_response, "mrdp", None)

        state_machine_state = None
        if hasattr(session, "state_machine") and session.state_machine:
            state_machine_state = getattr(session.state_machine, "current_state", None)

        # Build authoritative I13 trace from session first
        trace = self._trace_service.build_trace_from_session(
            session=session,
            kill_switch_state=kill_switch_state,
            reference_time=reference_time,
        )

        return self.build_timeline(
            transaction_id=session.transaction_id,
            intent=getattr(session, "intent", None),
            order=getattr(session, "order", None),
            payment=getattr(session, "payment", None),
            binding_context=getattr(session, "binding_context", None),
            integrity_result=getattr(session, "integrity_result", None),
            binding_outcome=getattr(session, "binding_outcome", None),
            kill_switch_state=kill_switch_state,
            kill_switch_record=getattr(session, "kill_switch_record", None),
            evidence_bundle=getattr(session, "evidence_bundle", None),
            events=getattr(session, "events", None),
            mrdp=mrdp,
            state_machine_state=state_machine_state,
            integrity_trace=trace,
            reference_time=reference_time,
        )

    def verify_timeline(
        self,
        timeline: IntegrityCheckpointTimeline,
    ) -> ChainVerificationResult:
        """Validates hash chain continuity and fingerprints of an existing checkpoint timeline."""
        return verify_checkpoint_chain(timeline.checkpoints)
