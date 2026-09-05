"""Deterministic Checkpoint Engine for Innovation I14 — Integrity Checkpoints.

Constructs, links, and validates chronological integrity checkpoints across transaction boundaries.
Integrates strictly with T04 (Integrity Authority), I8 (Binding), I9 (Kill Switch),
and consumes I13 (Trace & Localization) without duplicating fault localization logic.

Core Invariant:
AI proposes -> evidence proves -> deterministic logic decides.
I14 is purely a verification-boundary and timeline recording layer. Zero authoritative LLM logic.
"""
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
import uuid

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.intent import IntentContract
from backend.app.domain.models.integrity import IntegrityResult, MRDP
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.domain.models.evidence import Evidence, EvidenceBundle, CanonicalEvent
from backend.app.domain.binding.contracts import BindingContext, BindingVerificationOutcome
from backend.app.domain.kill_switch.contracts import KillSwitchState, KillSwitchRecord
from backend.app.domain.trace.contracts import LifecycleStage, StageIntegrityStatus, IntegrityTrace
from backend.app.domain.trace.engine import DeterministicTraceEngine
from backend.app.domain.checkpoint.contracts import (
    CheckpointType,
    CheckpointStatus,
    IntegrityCheckpoint,
    IntegrityCheckpointTimeline,
    compute_checkpoint_fingerprint,
    verify_checkpoint_chain,
)


STAGE_TO_CHECKPOINT_TYPE: Dict[LifecycleStage, CheckpointType] = {
    LifecycleStage.INTENT: CheckpointType.INTENT_AUTHORIZED,
    LifecycleStage.AGENT: CheckpointType.AGENT_ACTION_AUTHORIZED,
    LifecycleStage.MERCHANT: CheckpointType.MERCHANT_OFFER_VERIFIED,
    LifecycleStage.ORDER: CheckpointType.ORDER_CREATED,
    LifecycleStage.ATTEMPT: CheckpointType.PAYMENT_ATTEMPT_CREATED,
    LifecycleStage.PAYMENT: CheckpointType.PAYMENT_AUTHORIZED,
    LifecycleStage.GATEWAY: CheckpointType.PAYMENT_CAPTURE_VERIFIED,
    LifecycleStage.COMPLETION: CheckpointType.COMPLETION_VERIFIED,
}

STAGE_DEFAULT_VERIFIED_FIELDS: Dict[LifecycleStage, List[str]] = {
    LifecycleStage.INTENT: ["currency", "expires_at", "intent_id", "item_id", "max_total"],
    LifecycleStage.AGENT: ["agent_id", "intent_id", "issued_by"],
    LifecycleStage.MERCHANT: ["catalog_item", "merchant_id", "offer_terms"],
    LifecycleStage.ORDER: ["order_amount", "order_currency", "order_id", "order_receipt"],
    LifecycleStage.ATTEMPT: ["attempt_id", "attempt_limit", "single_use_token"],
    LifecycleStage.PAYMENT: ["authorized_amount", "currency", "payment_id", "recipient"],
    LifecycleStage.GATEWAY: ["capture_status", "gateway_status", "signature_verified"],
    LifecycleStage.COMPLETION: ["final_integrity", "state_machine_transition"],
}


class DeterministicCheckpointEngine:
    """
    Deterministic checkpoint generator and chain validator.
    Evaluates each boundary 1..8 and forms a tamper-evident hash-linked sequence.
    """

    @classmethod
    def generate_timeline(
        cls,
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
        """
        Generates an authoritative, deterministic IntegrityCheckpointTimeline.
        Consumes I13 trace information to avoid duplicate localization logic.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        # Synthesize canonical binding context if not explicitly provided but intent & order exist
        resolved_binding_ctx = binding_context
        if resolved_binding_ctx is None and intent is not None and order is not None:
            merchant_id = getattr(order, "notes", {}).get("merchant_id", "merch_acme_corp")
            resolved_binding_ctx = BindingContext(
                intent_id=intent.intent_id,
                agent_id=intent.issued_by,
                merchant_id=merchant_id,
                transaction_id=transaction_id,
                order_id=order.order_id,
                attempt_id="att_1",
                created_at=ref_time,
            )

        # 1. Obtain authoritative I13 trace if not provided
        trace = integrity_trace
        if trace is None:
            trace = DeterministicTraceEngine.build_trace(
                transaction_id=transaction_id,
                intent=intent,
                order=order,
                payment=payment,
                binding_context=resolved_binding_ctx,
                binding_outcome=binding_outcome,
                integrity_result=integrity_result,
                kill_switch_state=kill_switch_state,
                kill_switch_record=kill_switch_record,
                evidence_bundle=evidence_bundle,
                evidence_list=evidence_list,
                events=events,
                mrdp=mrdp,
                state_machine_state=state_machine_state,
                reference_time=ref_time,
                governance_version=governance_version,
            )

        # Determine overall integrity decision from T04
        t04_decision = integrity_result.status if integrity_result else IntegrityStatus.UNKNOWN
        binding_dec_str = "VALID" if (binding_outcome and binding_outcome.is_valid) else (
            "INVALID" if binding_outcome else "NOT_EVALUATED"
        )

        # 2. Build 8 checkpoints in strict chronological sequence (1 to 8)
        checkpoints: List[IntegrityCheckpoint] = []
        prev_cp_id: Optional[str] = None
        prev_cp_fingerprint: Optional[str] = None

        has_unknown = False

        # Build map of stage sequence to trace step
        steps_by_seq = {s.sequence: s for s in trace.steps}

        for seq in range(1, 9):
            step = steps_by_seq.get(seq)
            if step is None:
                continue

            stage = step.stage
            cp_type = STAGE_TO_CHECKPOINT_TYPE[stage]

            # Map StageIntegrityStatus to CheckpointStatus
            if step.status == StageIntegrityStatus.CONFIRMED_VALID:
                cp_status = CheckpointStatus.VALID
                verified_fields = STAGE_DEFAULT_VERIFIED_FIELDS.get(stage, [])
                missing_ev: List[str] = []
            elif step.status == StageIntegrityStatus.DIVERGENCE_DETECTED:
                cp_status = CheckpointStatus.INVALID
                verified_fields = []
                missing_ev = []
            elif step.status == StageIntegrityStatus.UNKNOWN:
                cp_status = CheckpointStatus.UNKNOWN
                verified_fields = []
                missing_ev = list(trace.missing_evidence)
                has_unknown = True
            elif step.status == StageIntegrityStatus.UNREACHED:
                cp_status = CheckpointStatus.NOT_REACHED
                verified_fields = []
                missing_ev = []
            else:
                cp_status = CheckpointStatus.UNKNOWN
                verified_fields = []
                missing_ev = []
                has_unknown = True

            # Sanitize findings and evidence refs
            clean_findings = [cls._sanitize_text(f) for f in step.findings]
            clean_ev_refs = sorted(str(ref) for ref in step.evidence_refs)

            cp_id = f"cp_{transaction_id}_{seq}_{cp_type.value.lower()}"

            # Compute canonical SHA-256 fingerprint
            fingerprint = compute_checkpoint_fingerprint(
                transaction_id=transaction_id,
                checkpoint_type=cp_type.value,
                sequence=seq,
                lifecycle_stage=stage.value,
                status=cp_status.value,
                verified_fields=verified_fields,
                evidence_refs=clean_ev_refs,
                integrity_decision=t04_decision.value,
                binding_decision=binding_dec_str,
                execution_state=kill_switch_state.value,
                missing_evidence=missing_ev,
                findings=clean_findings,
                governance_version=governance_version,
                previous_checkpoint_fingerprint=prev_cp_fingerprint,
                reproducibility_reference=reproducibility_reference,
            )

            checkpoint = IntegrityCheckpoint(
                checkpoint_id=cp_id,
                transaction_id=transaction_id,
                checkpoint_type=cp_type,
                sequence=seq,
                lifecycle_stage=stage,
                status=cp_status,
                verified_fields=sorted(verified_fields),
                evidence_refs=clean_ev_refs,
                integrity_decision=t04_decision,
                binding_decision=binding_dec_str,
                execution_state=kill_switch_state,
                missing_evidence=sorted(missing_ev),
                findings=sorted(clean_findings),
                governance_version=governance_version,
                reproducibility_reference=reproducibility_reference,
                previous_checkpoint_id=prev_cp_id,
                previous_checkpoint_fingerprint=prev_cp_fingerprint,
                fingerprint=fingerprint,
                created_at=step.timestamp or ref_time,
            )

            checkpoints.append(checkpoint)
            prev_cp_id = checkpoint.checkpoint_id
            prev_cp_fingerprint = checkpoint.fingerprint

        # 3. Determine last_valid_checkpoint and first_invalid_checkpoint
        last_valid: Optional[IntegrityCheckpoint] = None
        first_invalid: Optional[IntegrityCheckpoint] = None

        # Last valid checkpoint: highest sequence VALID checkpoint before divergence/unknown
        for cp in checkpoints:
            if cp.status == CheckpointStatus.VALID:
                if first_invalid is None and not has_unknown:
                    last_valid = cp
                elif first_invalid is None and has_unknown:
                    # Only update if no preceding unknown
                    last_valid = cp
            elif cp.status == CheckpointStatus.INVALID:
                if first_invalid is None:
                    first_invalid = cp
            elif cp.status == CheckpointStatus.UNKNOWN:
                # Stop advancing last_valid once an unknown boundary is encountered
                break

        # If first_invalid wasn't found in contiguous loop above, scan for earliest invalid
        if first_invalid is None:
            for cp in checkpoints:
                if cp.status == CheckpointStatus.INVALID:
                    first_invalid = cp
                    break

        # 4. Verify checkpoint chain
        chain_verification = verify_checkpoint_chain(checkpoints)

        return IntegrityCheckpointTimeline(
            transaction_id=transaction_id,
            checkpoints=checkpoints,
            last_valid_checkpoint=last_valid,
            first_invalid_checkpoint=first_invalid,
            has_unknown_checkpoints=has_unknown,
            chain_verification=chain_verification,
            governance_version=governance_version,
            reproducibility_reference=reproducibility_reference,
            generated_at=ref_time,
        )

    @classmethod
    def _sanitize_text(cls, text: str) -> str:
        """Sanitizes sensitive values from findings text."""
        if not text:
            return ""
        redacted = re.sub(
            r"(secret|token|api_key|password|signature|key)\s*[:=]\s*[^\s,;]+",
            r"\1=[REDACTED]",
            text,
            flags=re.IGNORECASE,
        )
        return redacted

    build_timeline = generate_timeline
