"""
Decision Reproducibility Certificate for TarkaRaksha Governance (I3.3).

Provides a tamper-detectable, deterministic certificate attributing decisions to:
- decision (IntegrityStatus / DecisionAction outcome)
- intent_hash
- evidence_hash
- event_chain_hash
- rules_version
- policy_version
- decision_timestamp

Note: This is a deterministic engineering provenance certificate, NOT a legal or regulatory certificate.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.governance.contracts import (
    DEFAULT_POLICY_VERSION,
    DEFAULT_RULES_VERSION,
)
from backend.app.domain.governance.record import (
    canonical_repr_for_hashing,
    compute_deterministic_hash,
)
from backend.app.domain.models.enums import IntegrityStatus
from backend.app.domain.models.evidence import CanonicalEvent, Evidence
from backend.app.domain.models.intent import IntentContract


def compute_intent_hash(intent: IntentContract) -> str:
    """Computes deterministic SHA-256 hash over canonical IntentContract."""
    return compute_deterministic_hash(intent.model_dump())


def compute_evidence_hash(evidence: List[Evidence]) -> str:
    """Computes deterministic SHA-256 hash over canonical ordered Evidence list."""
    sorted_ev = sorted(evidence, key=lambda e: (e.observed_at, e.evidence_id))
    return compute_deterministic_hash([e.model_dump() for e in sorted_ev])


def compute_event_chain_hash(events: List[CanonicalEvent]) -> str:
    """Computes deterministic SHA-256 hash over canonical ordered CanonicalEvent list."""
    sorted_events = sorted(events, key=lambda e: (e.timestamp, e.event_id))
    return compute_deterministic_hash([e.model_dump() for e in sorted_events])


class DecisionCertificateVerificationResult(BaseModel):
    """Result of deterministic certificate validation."""
    is_valid: bool
    mutations: List[str] = Field(default_factory=list)
    explanation: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )


class DecisionReproducibilityCertificate(BaseModel):
    """
    Deterministic Decision Reproducibility Certificate (§10.3).
    Binds decision outcome to exact cryptographic hashes of intent, evidence,
    event-chain, and governance versions.
    """
    certificate_id: str
    transaction_id: str
    decision: IntegrityStatus
    intent_hash: str
    evidence_hash: str
    event_chain_hash: str
    rules_version: str = Field(default=DEFAULT_RULES_VERSION)
    policy_version: str = Field(default=DEFAULT_POLICY_VERSION)
    decision_timestamp: datetime
    certificate_signature_hash: str

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("decision_timestamp", mode="before")
    @classmethod
    def validate_timezone(cls, v: Any) -> datetime:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise TypeError(f"decision_timestamp must be datetime or ISO string, got {type(v).__name__}")
        if dt.tzinfo is None:
            raise ValueError("decision_timestamp must be timezone-aware (e.g. UTC)")
        return dt

    @classmethod
    def issue(
        cls,
        certificate_id: str,
        transaction_id: str,
        decision: IntegrityStatus,
        intent: IntentContract,
        events: List[CanonicalEvent],
        evidence: List[Evidence],
        decision_timestamp: datetime,
        rules_version: str = DEFAULT_RULES_VERSION,
        policy_version: str = DEFAULT_POLICY_VERSION,
    ) -> "DecisionReproducibilityCertificate":
        """
        Issues a new DecisionReproducibilityCertificate computed from the raw artifacts.
        """
        i_hash = compute_intent_hash(intent)
        ev_hash = compute_evidence_hash(evidence)
        chain_hash = compute_event_chain_hash(events)

        payload_to_sign = {
            "certificate_id": certificate_id.strip(),
            "transaction_id": transaction_id.strip(),
            "decision": decision.value if hasattr(decision, "value") else str(decision),
            "intent_hash": i_hash,
            "evidence_hash": ev_hash,
            "event_chain_hash": chain_hash,
            "rules_version": rules_version.strip(),
            "policy_version": policy_version.strip(),
            "decision_timestamp": decision_timestamp.astimezone(timezone.utc).isoformat(),
        }
        cert_hash = compute_deterministic_hash(payload_to_sign)

        return cls(
            certificate_id=certificate_id.strip(),
            transaction_id=transaction_id.strip(),
            decision=decision,
            intent_hash=i_hash,
            evidence_hash=ev_hash,
            event_chain_hash=chain_hash,
            rules_version=rules_version.strip(),
            policy_version=policy_version.strip(),
            decision_timestamp=decision_timestamp,
            certificate_signature_hash=cert_hash,
        )

    def verify_integrity(
        self,
        intent: Optional[IntentContract] = None,
        events: Optional[List[CanonicalEvent]] = None,
        evidence: Optional[List[Evidence]] = None,
    ) -> DecisionCertificateVerificationResult:
        """
        Deterministically verifies the certificate.
        1. Checks internal certificate_signature_hash integrity.
        2. If raw components are supplied, checks that their re-computed hashes match.
        """
        mutations = []

        # 1. Verify certificate internal signature
        payload_to_sign = {
            "certificate_id": self.certificate_id,
            "transaction_id": self.transaction_id,
            "decision": self.decision.value if hasattr(self.decision, "value") else str(self.decision),
            "intent_hash": self.intent_hash,
            "evidence_hash": self.evidence_hash,
            "event_chain_hash": self.event_chain_hash,
            "rules_version": self.rules_version,
            "policy_version": self.policy_version,
            "decision_timestamp": self.decision_timestamp.astimezone(timezone.utc).isoformat(),
        }
        expected_cert_hash = compute_deterministic_hash(payload_to_sign)
        if self.certificate_signature_hash != expected_cert_hash:
            mutations.append("CERTIFICATE_TAMPERED")

        # 2. Verify external components if provided
        if intent is not None:
            if compute_intent_hash(intent) != self.intent_hash:
                mutations.append("INTENT_HASH_MUTATION")

        if evidence is not None:
            if compute_evidence_hash(evidence) != self.evidence_hash:
                mutations.append("EVIDENCE_HASH_MUTATION")

        if events is not None:
            if compute_event_chain_hash(events) != self.event_chain_hash:
                mutations.append("EVENT_CHAIN_HASH_MUTATION")

        if mutations:
            return DecisionCertificateVerificationResult(
                is_valid=False,
                mutations=mutations,
                explanation=f"Certificate verification failed due to mutations: {', '.join(mutations)}",
            )

        return DecisionCertificateVerificationResult(
            is_valid=True,
            mutations=[],
            explanation="Certificate is valid, intact, and reproducibly verified.",
        )
