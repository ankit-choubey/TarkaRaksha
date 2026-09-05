"""Authoritative domain contracts for Innovation I14 — Integrity Checkpoints.

Provides immutable checkpoint models, lifecycle checkpoint types, status outcomes,
canonical SHA-256 fingerprinting, tamper-evident hash chaining, and timeline schemas.

Core Invariant:
AI proposes -> evidence proves -> deterministic logic decides.
I14 is a verification-boundary layer recording deterministic checkpoints. Zero authoritative LLM logic.
"""
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.kill_switch.contracts import KillSwitchState
from backend.app.domain.trace.contracts import LifecycleStage


class CheckpointType(str, Enum):
    """
    Authoritative transaction lifecycle verification checkpoints.
    Corresponds strictly to the 8 canonical stages in LifecycleStage:
    INTENT -> AGENT -> MERCHANT -> ORDER -> ATTEMPT -> PAYMENT -> GATEWAY -> COMPLETION.
    """
    INTENT_AUTHORIZED = "INTENT_AUTHORIZED"              # Stage 1: INTENT
    AGENT_ACTION_AUTHORIZED = "AGENT_ACTION_AUTHORIZED"  # Stage 2: AGENT
    MERCHANT_OFFER_VERIFIED = "MERCHANT_OFFER_VERIFIED"  # Stage 3: MERCHANT
    ORDER_CREATED = "ORDER_CREATED"                      # Stage 4: ORDER
    PAYMENT_ATTEMPT_CREATED = "PAYMENT_ATTEMPT_CREATED"  # Stage 5: ATTEMPT
    PAYMENT_AUTHORIZED = "PAYMENT_AUTHORIZED"            # Stage 6: PAYMENT
    PAYMENT_CAPTURE_VERIFIED = "PAYMENT_CAPTURE_VERIFIED"# Stage 7: GATEWAY
    COMPLETION_VERIFIED = "COMPLETION_VERIFIED"          # Stage 8: COMPLETION


class CheckpointStatus(str, Enum):
    """
    Deterministic status outcome for an integrity checkpoint.
    Invariant: UNKNOWN != VALID, NOT_REACHED != UNKNOWN != INVALID.
    """
    VALID = "VALID"              # Authoritative evidence proves checkpoint invariants passed
    INVALID = "INVALID"          # Authoritative evidence demonstrates invariant divergence / drift
    UNKNOWN = "UNKNOWN"          # Evidence unavailable, delayed, or unresolved; prevents false invalid/pass
    NOT_REACHED = "NOT_REACHED"  # Transaction legitimately halted/failed before reaching this boundary


def compute_checkpoint_fingerprint(
    transaction_id: str,
    checkpoint_type: str,
    sequence: int,
    lifecycle_stage: str,
    status: str,
    verified_fields: List[str],
    evidence_refs: List[str],
    integrity_decision: str,
    binding_decision: Optional[str],
    execution_state: str,
    missing_evidence: List[str],
    findings: List[str],
    governance_version: str,
    previous_checkpoint_fingerprint: Optional[str] = None,
    reproducibility_reference: Optional[str] = None,
) -> str:
    """
    Computes a deterministic, byte-canonical SHA-256 fingerprint over checkpoint inputs.
    Excludes non-deterministic or arbitrary wall-clock timestamps to guarantee replay reproducibility.
    """
    data = {
        "transaction_id": str(transaction_id),
        "checkpoint_type": str(checkpoint_type),
        "sequence": int(sequence),
        "lifecycle_stage": str(lifecycle_stage),
        "status": str(status),
        "verified_fields": sorted(str(f) for f in verified_fields),
        "evidence_refs": sorted(str(ref) for ref in evidence_refs),
        "integrity_decision": str(integrity_decision),
        "binding_decision": str(binding_decision) if binding_decision is not None else None,
        "execution_state": str(execution_state),
        "missing_evidence": sorted(str(me) for me in missing_evidence),
        "findings": sorted(str(f) for f in findings),
        "governance_version": str(governance_version),
        "previous_checkpoint_fingerprint": str(previous_checkpoint_fingerprint or ""),
        "reproducibility_reference": str(reproducibility_reference or ""),
    }
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class IntegrityCheckpoint(BaseModel):
    """
    Immutable, deterministic verification snapshot at a critical lifecycle boundary.
    Tied to preceding checkpoints via previous_checkpoint_fingerprint.
    """
    checkpoint_id: str
    transaction_id: str
    checkpoint_type: CheckpointType
    sequence: int  # 1 to 8
    lifecycle_stage: LifecycleStage
    status: CheckpointStatus
    verified_fields: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    integrity_decision: IntegrityStatus
    binding_decision: Optional[str] = None
    execution_state: KillSwitchState
    missing_evidence: List[str] = Field(default_factory=list)
    findings: List[str] = Field(default_factory=list)
    governance_version: str = "gov_v1.0.0"
    reproducibility_reference: Optional[str] = None
    previous_checkpoint_id: Optional[str] = None
    previous_checkpoint_fingerprint: Optional[str] = None
    fingerprint: str
    created_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("checkpoint_id", "transaction_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Identifier cannot be empty or whitespace")
        return v.strip()

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: int) -> int:
        if v < 1 or v > 8:
            raise ValueError(f"Sequence must be between 1 and 8 inclusive, got {v}")
        return v

    @field_validator("created_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v

    def verify_fingerprint(self) -> bool:
        """Verifies that stored fingerprint matches recomputed SHA-256 canonical digest."""
        computed = compute_checkpoint_fingerprint(
            transaction_id=self.transaction_id,
            checkpoint_type=self.checkpoint_type.value,
            sequence=self.sequence,
            lifecycle_stage=self.lifecycle_stage.value,
            status=self.status.value,
            verified_fields=self.verified_fields,
            evidence_refs=self.evidence_refs,
            integrity_decision=self.integrity_decision.value,
            binding_decision=self.binding_decision,
            execution_state=self.execution_state.value,
            missing_evidence=self.missing_evidence,
            findings=self.findings,
            governance_version=self.governance_version,
            previous_checkpoint_fingerprint=self.previous_checkpoint_fingerprint,
            reproducibility_reference=self.reproducibility_reference,
        )
        return computed == self.fingerprint


class ChainVerificationResult(BaseModel):
    """Deterministic outcome of validating a sequence of chained integrity checkpoints."""
    is_valid: bool
    violations: List[str] = Field(default_factory=list)
    verified_count: int = 0

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


def verify_checkpoint_chain(checkpoints: List[IntegrityCheckpoint]) -> ChainVerificationResult:
    """
    Validates a sequence of checkpoints:
    1. Sequence numbers are strictly increasing (1..N) without gaps.
    2. No duplicate sequence numbers.
    3. Each individual checkpoint's fingerprint matches its content.
    4. Each checkpoint correctly points to previous_checkpoint_id and previous_checkpoint_fingerprint.
    """
    if not checkpoints:
        return ChainVerificationResult(is_valid=True, violations=[], verified_count=0)

    violations: List[str] = []

    # Check order & duplicates
    seen_seqs = set()
    prev_cp: Optional[IntegrityCheckpoint] = None

    for idx, cp in enumerate(checkpoints):
        # Fingerprint integrity
        if not cp.verify_fingerprint():
            violations.append(
                f"Checkpoint '{cp.checkpoint_id}' (sequence {cp.sequence}) fingerprint mismatch"
            )

        # Duplicate check
        if cp.sequence in seen_seqs:
            violations.append(f"Duplicate checkpoint sequence {cp.sequence} detected for '{cp.checkpoint_id}'")
        seen_seqs.add(cp.sequence)

        # Continuity check: sequence must match expected contiguous order
        expected_seq = idx + 1
        if cp.sequence != expected_seq:
            violations.append(
                f"Checkpoint sequence gap or reordering: expected {expected_seq}, found {cp.sequence} on '{cp.checkpoint_id}'"
            )

        # Hash chain linking check
        if idx == 0:
            if cp.previous_checkpoint_id is not None or cp.previous_checkpoint_fingerprint is not None:
                violations.append(
                    f"Initial checkpoint '{cp.checkpoint_id}' must not have previous link"
                )
        else:
            assert prev_cp is not None
            if cp.previous_checkpoint_id != prev_cp.checkpoint_id:
                violations.append(
                    f"Checkpoint '{cp.checkpoint_id}' previous_checkpoint_id '{cp.previous_checkpoint_id}' does not match preceding '{prev_cp.checkpoint_id}'"
                )
            if cp.previous_checkpoint_fingerprint != prev_cp.fingerprint:
                violations.append(
                    f"Checkpoint '{cp.checkpoint_id}' previous_checkpoint_fingerprint does not match preceding fingerprint on '{prev_cp.checkpoint_id}'"
                )

        prev_cp = cp

    return ChainVerificationResult(
        is_valid=len(violations) == 0,
        violations=violations,
        verified_count=len(checkpoints),
    )


class IntegrityCheckpointTimeline(BaseModel):
    """
    Deterministic chronological timeline of integrity checkpoints across the transaction lifecycle.
    Identifies the last verified valid boundary, first invalid boundary, and chain verification status.
    """
    transaction_id: str
    checkpoints: List[IntegrityCheckpoint]
    last_valid_checkpoint: Optional[IntegrityCheckpoint] = None
    first_invalid_checkpoint: Optional[IntegrityCheckpoint] = None
    has_unknown_checkpoints: bool = False
    chain_verification: ChainVerificationResult
    governance_version: str = "gov_v1.0.0"
    reproducibility_reference: Optional[str] = None
    generated_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @field_validator("transaction_id")
    @classmethod
    def validate_tx_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("transaction_id cannot be empty")
        return v.strip()

    @field_validator("generated_at")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware (UTC)")
        return v
