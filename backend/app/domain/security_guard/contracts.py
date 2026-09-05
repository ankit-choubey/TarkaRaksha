"""TarkaRaksha E4 — Security / Threat Guard Contracts.

Defines deterministic data structures, threat codes, severity levels,
and security results for the threat guard composition layer.

Governing Invariant:
AI proposes. Evidence proves. Deterministic logic decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json


class SecurityStatus(str, Enum):
    """Deterministic security verdict status."""
    CLEAR = "CLEAR"
    HOLD = "HOLD"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"


class SecuritySeverity(str, Enum):
    """Deterministic severity classification.

    No arbitrary numerical risk scores.
    """
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"
    CRITICAL = "CRITICAL"


class SecurityThreatCode(str, Enum):
    """Deterministic machine-readable threat codes.

    Only threat codes supported by the domain and primitives are defined.
    """
    PROMPT_INJECTION = "PROMPT_INJECTION"
    AGENT_CAPABILITY_VIOLATION = "AGENT_CAPABILITY_VIOLATION"
    AGENT_ID_MISMATCH = "AGENT_ID_MISMATCH"
    INTENT_MISMATCH = "INTENT_MISMATCH"
    TRANSACTION_MISMATCH = "TRANSACTION_MISMATCH"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    STALE_MESSAGE = "STALE_MESSAGE"
    DUPLICATE_MESSAGE = "DUPLICATE_MESSAGE"
    EVIDENCE_INTEGRITY_FAILURE = "EVIDENCE_INTEGRITY_FAILURE"
    STATE_DESYNC = "STATE_DESYNC"
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"
    PROVIDER_STATE_UNKNOWN = "PROVIDER_STATE_UNKNOWN"


@dataclass(frozen=True)
class ThreatFinding:
    """Deterministic finding produced by a threat rule."""
    threat_code: SecurityThreatCode
    severity: SecuritySeverity
    recommended_action: str
    rule_id: str
    explanation: str
    observed_value: Optional[str] = None
    expected_value: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threat_code": self.threat_code.value,
            "severity": self.severity.value,
            "recommended_action": self.recommended_action,
            "rule_id": self.rule_id,
            "explanation": self.explanation,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "evidence_refs": list(self.evidence_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SecurityGuardContext:
    """Immutable context evaluated by the security threat guard."""
    transaction_id: str
    intent_id: str
    agent_id: str
    session_id: Optional[str] = None
    buyer_agent_id: Optional[str] = None
    merchant_agent_id: Optional[str] = None
    message_id: Optional[str] = None
    message_timestamp: Optional[datetime] = None
    message_content: Optional[str] = None
    message_hash: Optional[str] = None
    attempt_id: Optional[str] = None
    
    # Financial and intent boundaries (authoritative)
    authorized_max_total: Optional[int] = None  # Integer minor units (paise)
    authorized_currency: str = "INR"
    authorization_expires_at: Optional[datetime] = None
    current_time: Optional[datetime] = None
    
    # Observed action context
    proposed_amount: Optional[int] = None
    proposed_currency: Optional[str] = None
    requested_capability: Optional[str] = None
    
    # Existing primitives context
    local_state: Optional[str] = None
    provider_state: Optional[str] = None
    provider_error: Optional[str] = None
    
    # Evidence & integrity references
    stored_evidence_hash: Optional[str] = None
    recomputed_evidence_hash: Optional[str] = None
    evidence_payload: Optional[Dict[str, Any]] = None
    checkpoint_fingerprints: List[str] = field(default_factory=list)
    
    # Unverified / adversarial text payload (to check prompt-injection attempts)
    untrusted_payloads: List[str] = field(default_factory=list)

    # Replay tracking flags
    known_message_ids: List[str] = field(default_factory=list)
    consumed_attempt_ids: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SecurityGuardResult:
    """Authoritative deterministic verdict from the E4 Security Threat Guard."""
    security_status: SecurityStatus
    findings: List[ThreatFinding] = field(default_factory=list)
    transaction_id: str = ""
    intent_id: str = ""
    agent_id: str = ""
    kill_switch_triggered: bool = False
    kill_switch_reason: Optional[str] = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reproducibility_hash: str = ""
    evidence_refs: List[str] = field(default_factory=list)

    @classmethod
    def compute_hash(
        cls,
        status: SecurityStatus,
        findings: List[ThreatFinding],
        tx_id: str,
        intent_id: str,
        agent_id: str,
    ) -> str:
        """Deterministic hash computation over stable findings."""
        findings_repr = [
            f"{f.threat_code.value}:{f.severity.value}:{f.rule_id}:{f.observed_value}:{f.expected_value}"
            for f in sorted(findings, key=lambda x: (x.threat_code.value, x.rule_id))
        ]
        raw = f"{status.value}|{tx_id}|{intent_id}|{agent_id}|" + "|".join(findings_repr)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "security_status": self.security_status.value,
            "findings": [f.to_dict() for f in self.findings],
            "transaction_id": self.transaction_id,
            "intent_id": self.intent_id,
            "agent_id": self.agent_id,
            "kill_switch_triggered": self.kill_switch_triggered,
            "kill_switch_reason": self.kill_switch_reason,
            "evaluated_at": self.evaluated_at.isoformat(),
            "reproducibility_hash": self.reproducibility_hash,
            "evidence_refs": list(self.evidence_refs),
        }
