"""Integrity Trace Service for Innovation I13 — Integrity Trace / Fault Localization.

Orchestrates trace building from active runtime sessions (TransactionSession) or raw parameter inputs.
Completely deterministic and read-only.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.app.domain.trace.contracts import IntegrityTrace
from backend.app.domain.trace.engine import DeterministicTraceEngine
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.evidence import CanonicalEvent, Evidence, EvidenceBundle
from backend.app.domain.models.integrity import MRDP, IntegrityResult
from backend.app.domain.binding.contracts import (
    BindingContext,
    BindingVerificationOutcome,
)
from backend.app.domain.kill_switch.contracts import (
    KillSwitchRecord,
    KillSwitchState,
)
from backend.app.domain.models.enums import TransactionState


class IntegrityTraceService:
    """
    Service layer coordinator for generating deterministic IntegrityTraces.
    Used by TransactionService, Replay audit, and API endpoints.
    """

    def __init__(self, engine: Optional[DeterministicTraceEngine] = None):
        self._engine = engine or DeterministicTraceEngine

    def build_trace(
        self,
        transaction_id: str,
        intent: Optional[IntentContract] = None,
        order: Optional[ProviderOrder] = None,
        payment: Optional[ProviderPayment] = None,
        binding_context: Optional[BindingContext] = None,
        binding_outcome: Optional[BindingVerificationOutcome] = None,
        integrity_result: Optional[IntegrityResult] = None,
        kill_switch_state: KillSwitchState = KillSwitchState.RUNNING,
        kill_switch_record: Optional[KillSwitchRecord] = None,
        evidence_bundle: Optional[EvidenceBundle] = None,
        evidence_list: Optional[List[Evidence]] = None,
        events: Optional[List[CanonicalEvent]] = None,
        mrdp: Optional[MRDP] = None,
        state_machine_state: Optional[TransactionState] = None,
        reference_time: Optional[datetime] = None,
        governance_version: str = "gov_v1.0.0",
        trace_id: Optional[str] = None,
    ) -> IntegrityTrace:
        """Constructs an IntegrityTrace deterministically from provided parameters."""
        return self._engine.build_trace(
            transaction_id=transaction_id,
            intent=intent,
            order=order,
            payment=payment,
            binding_context=binding_context,
            binding_outcome=binding_outcome,
            integrity_result=integrity_result,
            kill_switch_state=kill_switch_state,
            kill_switch_record=kill_switch_record,
            evidence_bundle=evidence_bundle,
            evidence_list=evidence_list,
            events=events,
            mrdp=mrdp,
            state_machine_state=state_machine_state,
            reference_time=reference_time,
            governance_version=governance_version,
            trace_id=trace_id,
        )

    def build_trace_from_session(
        self,
        session: Any,
        kill_switch_state: KillSwitchState = KillSwitchState.RUNNING,
        reference_time: Optional[datetime] = None,
    ) -> IntegrityTrace:
        """Constructs an IntegrityTrace from a TransactionSession object."""
        mrdp = None
        if hasattr(session, "completed_response") and session.completed_response:
            mrdp = getattr(session.completed_response, "mrdp", None)

        state_machine_state = None
        if hasattr(session, "state_machine") and session.state_machine:
            state_machine_state = getattr(session.state_machine, "current_state", None)

        return self.build_trace(
            transaction_id=session.transaction_id,
            intent=getattr(session, "intent", None),
            order=getattr(session, "order", None),
            payment=getattr(session, "payment", None),
            binding_context=getattr(session, "binding_context", None),
            binding_outcome=getattr(session, "binding_outcome", None),
            integrity_result=getattr(session, "integrity_result", None),
            kill_switch_state=kill_switch_state,
            kill_switch_record=getattr(session, "kill_switch_record", None),
            evidence_bundle=getattr(session, "evidence_bundle", None),
            events=getattr(session, "events", None),
            mrdp=mrdp,
            state_machine_state=state_machine_state,
            reference_time=reference_time,
        )
