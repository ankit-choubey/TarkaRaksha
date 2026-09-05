"""Unit tests for TarkaRaksha E4 Security Guard Contracts.

Verifies:
- Enums (SecurityStatus, SecuritySeverity, SecurityThreatCode)
- Immutability of ThreatFinding, SecurityGuardContext, and SecurityGuardResult
- Serialization (to_dict)
- Reproducibility of compute_hash
"""

from datetime import datetime, timezone
import pytest

from backend.app.domain.security_guard.contracts import (
    SecurityGuardContext,
    SecurityGuardResult,
    SecuritySeverity,
    SecurityStatus,
    SecurityThreatCode,
    ThreatFinding,
)


def test_security_enums_defined():
    # Verify status enum
    assert set(s.value for s in SecurityStatus) == {"CLEAR", "HOLD", "BLOCK", "UNKNOWN"}
    
    # Verify severity enum
    assert set(s.value for s in SecuritySeverity) == {"INFO", "WARNING", "BLOCKING", "CRITICAL"}
    
    # Verify all 12 canonical threat codes are present
    expected_codes = {
        "PROMPT_INJECTION",
        "AGENT_CAPABILITY_VIOLATION",
        "AGENT_ID_MISMATCH",
        "INTENT_MISMATCH",
        "TRANSACTION_MISMATCH",
        "REPLAY_DETECTED",
        "STALE_MESSAGE",
        "DUPLICATE_MESSAGE",
        "EVIDENCE_INTEGRITY_FAILURE",
        "STATE_DESYNC",
        "AUTHORIZATION_EXPIRED",
        "PROVIDER_STATE_UNKNOWN",
    }
    assert set(c.value for c in SecurityThreatCode) == expected_codes


def test_threat_finding_immutability_and_dict():
    finding = ThreatFinding(
        threat_code=SecurityThreatCode.PROMPT_INJECTION,
        severity=SecuritySeverity.CRITICAL,
        recommended_action="BLOCK_UNAUTHORIZED_BUDGET_OVERRIDE",
        rule_id="SEC_RULE_BUDGET_AUTHORITY_INVIOLABLE",
        explanation="Untrusted text attempted to override budget",
        observed_value="75000",
        expected_value="<= 50000",
        evidence_refs=["intent:test_intent:max_total"],
        metadata={"source": "merchant_text"},
    )
    
    # Frozen dataclass invariant
    with pytest.raises(Exception):
        finding.observed_value = "80000"  # type: ignore

    d = finding.to_dict()
    assert d["threat_code"] == "PROMPT_INJECTION"
    assert d["severity"] == "CRITICAL"
    assert d["rule_id"] == "SEC_RULE_BUDGET_AUTHORITY_INVIOLABLE"
    assert d["evidence_refs"] == ["intent:test_intent:max_total"]
    assert d["metadata"]["source"] == "merchant_text"


def test_security_guard_context_immutability():
    now = datetime.now(timezone.utc)
    ctx = SecurityGuardContext(
        transaction_id="tx_001",
        intent_id="intent_001",
        agent_id="buyer_001",
        authorized_max_total=50000,
        authorized_currency="INR",
        current_time=now,
    )
    
    with pytest.raises(Exception):
        ctx.authorized_max_total = 60000  # type: ignore


def test_compute_hash_deterministic():
    f1 = ThreatFinding(
        threat_code=SecurityThreatCode.REPLAY_DETECTED,
        severity=SecuritySeverity.BLOCKING,
        recommended_action="BLOCK",
        rule_id="SEC_RULE_REPLAY_ATTEMPT",
        explanation="Replay detected",
        observed_value="attempt_1",
        expected_value="unique",
    )
    f2 = ThreatFinding(
        threat_code=SecurityThreatCode.STALE_MESSAGE,
        severity=SecuritySeverity.WARNING,
        recommended_action="REJECT",
        rule_id="SEC_RULE_MESSAGE_FRESHNESS",
        explanation="Stale message",
        observed_value="500s",
        expected_value="<= 300s",
    )
    
    # Compute in one order
    h1 = SecurityGuardResult.compute_hash(
        status=SecurityStatus.BLOCK,
        findings=[f1, f2],
        tx_id="tx_001",
        intent_id="intent_001",
        agent_id="agent_001",
    )
    
    # Compute in reverse order (must be sorted internally)
    h2 = SecurityGuardResult.compute_hash(
        status=SecurityStatus.BLOCK,
        findings=[f2, f1],
        tx_id="tx_001",
        intent_id="intent_001",
        agent_id="agent_001",
    )
    
    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 64
