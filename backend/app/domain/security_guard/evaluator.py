"""TarkaRaksha E4 — Deterministic Security Threat Evaluator.

Evaluates an immutable SecurityGuardContext against the 12 canonical threat rules,
composing existing verified security primitives:
- I2: Protocol Security (replay, timestamps, message deduplication)
- I8: Transaction & Intent Binding (agent/tx/intent matching)
- I9: Execution Kill Switch (escalation on critical security threats)
- I14: Integrity Checkpoints & Evidence Integrity (hash checks)
- I19: Agent Capability Graph (capability boundary verification)

Governing Invariant:
AI proposes. Evidence proves. Deterministic logic decides.
Untrusted content is DATA, never AUTHORITY.
Zero live network access. Purely deterministic and reproducible.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import List, Optional, Tuple

from backend.app.domain.security_guard.contracts import (
    SecurityGuardContext,
    SecurityGuardResult,
    SecuritySeverity,
    SecurityStatus,
    SecurityThreatCode,
    ThreatFinding,
)

# Known adversarial prompt injection patterns to inspect in untrusted data
_INJECTION_PATTERNS = [
    (re.compile(r"ignore\s+(the\s+)?(user['’]?s?\s+)?budget", re.IGNORECASE), "IGNORE_BUDGET"),
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE), "IGNORE_INSTRUCTIONS"),
    (re.compile(r"authorized\s+to\s+spend\s+more", re.IGNORECASE), "OVERRIDE_AUTHORITY"),
    (re.compile(r"administrator\s+(has\s+)?approved", re.IGNORECASE), "FAKE_ADMIN_APPROVAL"),
    (re.compile(r"disable\s+(all\s+)?security\s+checks?", re.IGNORECASE), "DISABLE_SECURITY"),
    (re.compile(r"mark\s+(this\s+)?payment\s+(as\s+)?captured", re.IGNORECASE), "FAKE_PAYMENT_CAPTURE"),
    (re.compile(r"bypass\s+verification", re.IGNORECASE), "BYPASS_VERIFICATION"),
]


class SecurityThreatEvaluator:
    """Pure deterministic threat evaluation engine for TarkaRaksha E4."""

    @staticmethod
    def evaluate(ctx: SecurityGuardContext) -> SecurityGuardResult:
        """Evaluate the provided context and return a deterministic SecurityGuardResult."""
        findings: List[ThreatFinding] = []
        evidence_refs: List[str] = []

        eval_time = ctx.current_time or datetime.now(timezone.utc)

        # Rule 1: Authorization Expiration (Threat 12)
        SecurityThreatEvaluator._check_authorization_expired(ctx, eval_time, findings, evidence_refs)

        # Rule 2: Agent Identity & Binding (Threat 3, Threat 4, Threat 5)
        SecurityThreatEvaluator._check_bindings(ctx, findings, evidence_refs)

        # Rule 3: Replay & Message Freshness (Threat 6, Threat 7, Threat 8)
        SecurityThreatEvaluator._check_message_and_replay(ctx, eval_time, findings, evidence_refs)

        # Rule 4: Capability Boundaries (Threat 2)
        SecurityThreatEvaluator._check_capability_abuse(ctx, findings, evidence_refs)

        # Rule 5: Evidence Integrity & Checkpoint Tampering (Threat 9)
        SecurityThreatEvaluator._check_evidence_integrity(ctx, findings, evidence_refs)

        # Rule 6: State Consistency & Provider Ambiguity (Threat 10, Threat 11)
        SecurityThreatEvaluator._check_state_and_provider(ctx, findings, evidence_refs)

        # Rule 7: Untrusted Content & Prompt Injection Isolation (Threat 1)
        SecurityThreatEvaluator._check_prompt_injection(ctx, findings, evidence_refs)

        # Deterministic Verdict and Kill-Switch Synthesis
        status, kill_switch, kill_reason = SecurityThreatEvaluator._synthesize_verdict(findings)

        rep_hash = SecurityGuardResult.compute_hash(
            status=status,
            findings=findings,
            tx_id=ctx.transaction_id,
            intent_id=ctx.intent_id,
            agent_id=ctx.agent_id,
        )

        return SecurityGuardResult(
            security_status=status,
            findings=findings,
            transaction_id=ctx.transaction_id,
            intent_id=ctx.intent_id,
            agent_id=ctx.agent_id,
            kill_switch_triggered=kill_switch,
            kill_switch_reason=kill_reason,
            evaluated_at=eval_time,
            reproducibility_hash=rep_hash,
            evidence_refs=list(set(evidence_refs)),
        )

    @staticmethod
    def _check_authorization_expired(
        ctx: SecurityGuardContext,
        eval_time: datetime,
        findings: List[ThreatFinding],
        evidence_refs: List[str],
    ) -> None:
        """Threat 12: Expired authorization must never be silently accepted."""
        if ctx.authorization_expires_at is not None:
            # Ensure timezone awareness match
            exp = ctx.authorization_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            curr = eval_time if eval_time.tzinfo is not None else eval_time.replace(tzinfo=timezone.utc)

            if curr > exp:
                findings.append(
                    ThreatFinding(
                        threat_code=SecurityThreatCode.AUTHORIZATION_EXPIRED,
                        severity=SecuritySeverity.BLOCKING,
                        recommended_action="BLOCK_AND_REQUIRE_NEW_AUTHORIZATION",
                        rule_id="SEC_RULE_AUTH_EXPIRED",
                        explanation=f"Authorization expired at {exp.isoformat()}; evaluation time is {curr.isoformat()}",
                        observed_value=curr.isoformat(),
                        expected_value=f"<= {exp.isoformat()}",
                        evidence_refs=[f"intent:{ctx.intent_id}:expires_at"],
                    )
                )
                evidence_refs.append(f"intent:{ctx.intent_id}:expires_at")

    @staticmethod
    def _check_bindings(
        ctx: SecurityGuardContext,
        findings: List[ThreatFinding],
        evidence_refs: List[str],
    ) -> None:
        """Threats 3, 4, 5: Agent ID, Transaction, and Intent Mismatches."""
        # Check Agent ID matching if expected buyer or merchant is specified
        if ctx.buyer_agent_id and ctx.agent_id != ctx.buyer_agent_id:
            # If not matching buyer, check if merchant is specified and matching
            if ctx.merchant_agent_id and ctx.agent_id == ctx.merchant_agent_id:
                pass  # Recognized merchant agent
            else:
                findings.append(
                    ThreatFinding(
                        threat_code=SecurityThreatCode.AGENT_ID_MISMATCH,
                        severity=SecuritySeverity.CRITICAL,
                        recommended_action="REJECT_AND_ISOLATE_AGENT",
                        rule_id="SEC_RULE_AGENT_BINDING",
                        explanation=f"Incoming agent_id '{ctx.agent_id}' does not match expected bound agent(s)",
                        observed_value=ctx.agent_id,
                        expected_value=ctx.buyer_agent_id if not ctx.merchant_agent_id else f"{ctx.buyer_agent_id}|{ctx.merchant_agent_id}",
                        evidence_refs=[f"binding:agent:{ctx.agent_id}"],
                    )
                )
                evidence_refs.append(f"binding:agent:{ctx.agent_id}")

        # Intent mismatch check from metadata
        if "expected_intent_id" in ctx.metadata and ctx.metadata["expected_intent_id"] != ctx.intent_id:
            findings.append(
                ThreatFinding(
                    threat_code=SecurityThreatCode.INTENT_MISMATCH,
                    severity=SecuritySeverity.CRITICAL,
                    recommended_action="REJECT_TRANSACTION_MISALIGNMENT",
                    rule_id="SEC_RULE_INTENT_BINDING",
                    explanation=f"Referenced intent_id '{ctx.intent_id}' differs from bound intent '{ctx.metadata['expected_intent_id']}'",
                    observed_value=ctx.intent_id,
                    expected_value=ctx.metadata["expected_intent_id"],
                    evidence_refs=[f"intent:{ctx.intent_id}"],
                )
            )
            evidence_refs.append(f"intent:{ctx.intent_id}")

        # Transaction mismatch check from metadata
        if "expected_transaction_id" in ctx.metadata and ctx.metadata["expected_transaction_id"] != ctx.transaction_id:
            findings.append(
                ThreatFinding(
                    threat_code=SecurityThreatCode.TRANSACTION_MISMATCH,
                    severity=SecuritySeverity.CRITICAL,
                    recommended_action="REJECT_CONTEXT_MISALIGNMENT",
                    rule_id="SEC_RULE_TX_BINDING",
                    explanation=f"Evidence/payload transaction_id '{ctx.transaction_id}' does not match target context '{ctx.metadata['expected_transaction_id']}'",
                    observed_value=ctx.transaction_id,
                    expected_value=ctx.metadata["expected_transaction_id"],
                    evidence_refs=[f"tx:{ctx.transaction_id}"],
                )
            )
            evidence_refs.append(f"tx:{ctx.transaction_id}")

    @staticmethod
    def _check_message_and_replay(
        ctx: SecurityGuardContext,
        eval_time: datetime,
        findings: List[ThreatFinding],
        evidence_refs: List[str],
    ) -> None:
        """Threats 6, 7, 8: Replay, Stale Message, and Duplicate Delivery."""
        # 1. Stale Message Check
        if ctx.message_timestamp is not None:
            msg_t = ctx.message_timestamp
            if msg_t.tzinfo is None:
                msg_t = msg_t.replace(tzinfo=timezone.utc)
            curr = eval_time if eval_time.tzinfo is not None else eval_time.replace(tzinfo=timezone.utc)
            delta_seconds = (curr - msg_t).total_seconds()
            
            # Default tolerance: 300 seconds (5 minutes) unless overridden in metadata
            max_age = ctx.metadata.get("max_message_age_seconds", 300)
            if delta_seconds > max_age:
                findings.append(
                    ThreatFinding(
                        threat_code=SecurityThreatCode.STALE_MESSAGE,
                        severity=SecuritySeverity.WARNING,
                        recommended_action="REJECT_STALE_MESSAGE",
                        rule_id="SEC_RULE_MESSAGE_FRESHNESS",
                        explanation=f"Message age {delta_seconds:.1f}s exceeds maximum allowed freshness window ({max_age}s)",
                        observed_value=f"{delta_seconds:.1f}s",
                        expected_value=f"<= {max_age}s",
                        evidence_refs=[f"msg:{ctx.message_id or 'unknown'}:timestamp"],
                    )
                )
                evidence_refs.append(f"msg:{ctx.message_id or 'unknown'}:timestamp")

        # 2. Replay & Duplicate Message Check
        if ctx.attempt_id and ctx.attempt_id in ctx.consumed_attempt_ids:
            findings.append(
                ThreatFinding(
                    threat_code=SecurityThreatCode.REPLAY_DETECTED,
                    severity=SecuritySeverity.BLOCKING,
                    recommended_action="BLOCK_REPLAY_ATTEMPT",
                    rule_id="SEC_RULE_REPLAY_ATTEMPT",
                    explanation=f"Execution attempt_id '{ctx.attempt_id}' has already been consumed and processed",
                    observed_value=ctx.attempt_id,
                    expected_value="unique_unconsumed_attempt_id",
                    evidence_refs=[f"attempt:{ctx.attempt_id}"],
                )
            )
            evidence_refs.append(f"attempt:{ctx.attempt_id}")

        elif ctx.message_id and ctx.message_id in ctx.known_message_ids:
            # Duplicate message delivery (distinguished from replay execution)
            findings.append(
                ThreatFinding(
                    threat_code=SecurityThreatCode.DUPLICATE_MESSAGE,
                    severity=SecuritySeverity.INFO,
                    recommended_action="DEDUPLICATE_MESSAGE",
                    rule_id="SEC_RULE_MESSAGE_DEDUP",
                    explanation=f"Message ID '{ctx.message_id}' was already received; treated as duplicate delivery (not duplicate financial execution)",
                    observed_value=ctx.message_id,
                    expected_value="new_message_id",
                    evidence_refs=[f"msg:{ctx.message_id}"],
                )
            )
            evidence_refs.append(f"msg:{ctx.message_id}")

    @staticmethod
    def _check_capability_abuse(
        ctx: SecurityGuardContext,
        findings: List[ThreatFinding],
        evidence_refs: List[str],
    ) -> None:
        """Threat 2: Agent Capability Abuse (e.g. refund/transfer exceeding declared ceiling)."""
        if ctx.requested_capability:
            allowed_caps = ctx.metadata.get("allowed_capabilities", [])
            if allowed_caps and ctx.requested_capability not in allowed_caps:
                findings.append(
                    ThreatFinding(
                        threat_code=SecurityThreatCode.AGENT_CAPABILITY_VIOLATION,
                        severity=SecuritySeverity.BLOCKING,
                        recommended_action="BLOCK_CAPABILITY_ABUSE",
                        rule_id="SEC_RULE_CAPABILITY_SCOPE",
                        explanation=f"Agent '{ctx.agent_id}' requested capability '{ctx.requested_capability}' which is not in its allowed capabilities: {allowed_caps}",
                        observed_value=ctx.requested_capability,
                        expected_value=f"in {allowed_caps}",
                        evidence_refs=[f"agent:{ctx.agent_id}:capabilities"],
                    )
                )
                evidence_refs.append(f"agent:{ctx.agent_id}:capabilities")

        # Cap financial limit for specific actions (e.g., refund ceiling)
        if ctx.proposed_amount is not None:
            max_capability_amount = ctx.metadata.get("max_capability_amount")
            if max_capability_amount is not None and ctx.proposed_amount > max_capability_amount:
                findings.append(
                    ThreatFinding(
                        threat_code=SecurityThreatCode.AGENT_CAPABILITY_VIOLATION,
                        severity=SecuritySeverity.BLOCKING,
                        recommended_action="BLOCK_CAPABILITY_AMOUNT_LIMIT",
                        rule_id="SEC_RULE_CAPABILITY_CEILING",
                        explanation=f"Proposed amount {ctx.proposed_amount} exceeds agent '{ctx.agent_id}' capability limit of {max_capability_amount}",
                        observed_value=str(ctx.proposed_amount),
                        expected_value=f"<= {max_capability_amount}",
                        evidence_refs=[f"agent:{ctx.agent_id}:limit"],
                    )
                )
                evidence_refs.append(f"agent:{ctx.agent_id}:limit")

    @staticmethod
    def _check_evidence_integrity(
        ctx: SecurityGuardContext,
        findings: List[ThreatFinding],
        evidence_refs: List[str],
    ) -> None:
        """Threat 9: Tampered Evidence & Hash Chain Discrepancy."""
        if ctx.stored_evidence_hash is not None and ctx.recomputed_evidence_hash is not None:
            if ctx.stored_evidence_hash != ctx.recomputed_evidence_hash:
                findings.append(
                    ThreatFinding(
                        threat_code=SecurityThreatCode.EVIDENCE_INTEGRITY_FAILURE,
                        severity=SecuritySeverity.CRITICAL,
                        recommended_action="HOLD_AND_FLAG_EVIDENCE_TAMPER",
                        rule_id="SEC_RULE_EVIDENCE_HASH_MISMATCH",
                        explanation=f"Stored evidence hash '{ctx.stored_evidence_hash}' does not match recomputed hash '{ctx.recomputed_evidence_hash}'",
                        observed_value=ctx.recomputed_evidence_hash,
                        expected_value=ctx.stored_evidence_hash,
                        evidence_refs=[f"evidence:{ctx.transaction_id}:hash"],
                    )
                )
                evidence_refs.append(f"evidence:{ctx.transaction_id}:hash")

        # Checkpoint continuity validation
        if "checkpoint_verification_failed" in ctx.metadata and ctx.metadata["checkpoint_verification_failed"]:
            findings.append(
                ThreatFinding(
                    threat_code=SecurityThreatCode.EVIDENCE_INTEGRITY_FAILURE,
                    severity=SecuritySeverity.CRITICAL,
                    recommended_action="HOLD_CHECKPOINT_CHAIN_BROKEN",
                    rule_id="SEC_RULE_CHECKPOINT_CHAIN_INTEGRITY",
                    explanation="I14 checkpoint hash chain failed verification; internal consistency cannot be guaranteed",
                    observed_value="INVALID_CHAIN",
                    expected_value="VALID_HASH_CHAIN",
                    evidence_refs=[f"checkpoint_chain:{ctx.transaction_id}"],
                )
            )
            evidence_refs.append(f"checkpoint_chain:{ctx.transaction_id}")

    @staticmethod
    def _check_state_and_provider(
        ctx: SecurityGuardContext,
        findings: List[ThreatFinding],
        evidence_refs: List[str],
    ) -> None:
        """Threats 10 & 11: State Desync and Provider State Ambiguity."""
        # 1. State Desynchronization (Local vs Provider)
        if ctx.local_state and ctx.provider_state:
            # Conflicting authoritative states
            desync_pairs = [
                ("AUTHORIZED", "CAPTURED"),
                ("CAPTURED", "FAILED"),
                ("AUTHORIZED", "REFUNDED"),
            ]
            if (ctx.local_state, ctx.provider_state) in desync_pairs:
                findings.append(
                    ThreatFinding(
                        threat_code=SecurityThreatCode.STATE_DESYNC,
                        severity=SecuritySeverity.BLOCKING,
                        recommended_action="HOLD_FOR_STATE_RECONCILIATION",
                        rule_id="SEC_RULE_STATE_DESYNC",
                        explanation=f"Local state '{ctx.local_state}' is desynchronized with authoritative provider state '{ctx.provider_state}'",
                        observed_value=ctx.local_state,
                        expected_value=ctx.provider_state,
                        evidence_refs=[f"tx:{ctx.transaction_id}:state"],
                    )
                )
                evidence_refs.append(f"tx:{ctx.transaction_id}:state")

        # 2. Provider State Ambiguity (UNKNOWN first-class state)
        if ctx.provider_state in ("UNKNOWN", "UNRESOLVED", None) and ctx.provider_error:
            findings.append(
                ThreatFinding(
                    threat_code=SecurityThreatCode.PROVIDER_STATE_UNKNOWN,
                    severity=SecuritySeverity.WARNING,
                    recommended_action="HOLD_AS_UNKNOWN_NEVER_FORCE_PASS",
                    rule_id="SEC_RULE_PROVIDER_AMBIGUITY",
                    explanation=f"Provider state is ambiguous or unverified: {ctx.provider_error}",
                    observed_value=str(ctx.provider_state),
                    expected_value="VERIFIED_PROVIDER_STATE",
                    evidence_refs=[f"provider:{ctx.transaction_id}:error"],
                )
            )
            evidence_refs.append(f"provider:{ctx.transaction_id}:error")

    @staticmethod
    def _check_prompt_injection(
        ctx: SecurityGuardContext,
        findings: List[ThreatFinding],
        evidence_refs: List[str],
    ) -> None:
        """Threat 1: Prompt Injection.

        Untrusted content is DATA, never AUTHORITY.
        1. Detect adversarial prompt injection patterns in untrusted payloads.
        2. Ensure that malicious text has not modified authoritative constraints
           (e.g. proposed_amount exceeding authorized_max_total).
        """
        # Scan untrusted payloads for malicious instructions
        detected_injections = []
        for payload in ctx.untrusted_payloads:
            if not payload:
                continue
            for pattern, name in _INJECTION_PATTERNS:
                if pattern.search(payload):
                    detected_injections.append(f"{name} in payload: '{payload[:60]}...'")

        if detected_injections:
            findings.append(
                ThreatFinding(
                    threat_code=SecurityThreatCode.PROMPT_INJECTION,
                    severity=SecuritySeverity.WARNING,
                    recommended_action="ISOLATE_DATA_ENFORCE_CONTRACT",
                    rule_id="SEC_RULE_PROMPT_INJECTION_DETECTED",
                    explanation=f"Adversarial prompt injection pattern detected in untrusted content; treated strictly as DATA, not AUTHORITY: {'; '.join(detected_injections)}",
                    observed_value="INJECTION_ATTEMPT_DETECTED",
                    expected_value="BENIGN_UNTRUSTED_DATA",
                    evidence_refs=[f"payload:{ctx.transaction_id}:untrusted_text"],
                    metadata={"detections": detected_injections},
                )
            )
            evidence_refs.append(f"payload:{ctx.transaction_id}:untrusted_text")

        # Core Invariant Check: Did the proposed amount exceed the immutable authorized budget?
        # Even if prompt injection attempted to override budget, the deterministic constraint holds!
        if (
            ctx.authorized_max_total is not None
            and ctx.proposed_amount is not None
            and ctx.proposed_amount > ctx.authorized_max_total
        ):
            # Deterministic violation of intent boundary
            findings.append(
                ThreatFinding(
                    threat_code=SecurityThreatCode.PROMPT_INJECTION,
                    severity=SecuritySeverity.CRITICAL,
                    recommended_action="BLOCK_UNAUTHORIZED_BUDGET_OVERRIDE",
                    rule_id="SEC_RULE_BUDGET_AUTHORITY_INVIOLABLE",
                    explanation=f"Proposed amount {ctx.proposed_amount} exceeds authoritative intent max_total of {ctx.authorized_max_total}; untrusted text cannot override budget authority",
                    observed_value=str(ctx.proposed_amount),
                    expected_value=f"<= {ctx.authorized_max_total}",
                    evidence_refs=[f"intent:{ctx.intent_id}:max_total"],
                )
            )
            evidence_refs.append(f"intent:{ctx.intent_id}:max_total")

    @staticmethod
    def _synthesize_verdict(findings: List[ThreatFinding]) -> Tuple[SecurityStatus, bool, Optional[str]]:
        """Synthesize overall SecurityStatus and determine if I9 Kill-Switch is triggered.

        Deterministic rules:
        - Any CRITICAL finding -> BLOCK status + Kill-Switch triggered.
        - Any BLOCKING finding -> BLOCK status (Kill-Switch triggered if severity warrants).
        - Any WARNING finding (or PROVIDER_STATE_UNKNOWN) without BLOCKING -> HOLD or UNKNOWN status.
        - Only INFO findings (e.g. DUPLICATE_MESSAGE) or no findings -> CLEAR status.
        """
        if not findings:
            return SecurityStatus.CLEAR, False, None

        has_critical = any(f.severity == SecuritySeverity.CRITICAL for f in findings)
        has_blocking = any(f.severity == SecuritySeverity.BLOCKING for f in findings)
        has_provider_unknown = any(f.threat_code == SecurityThreatCode.PROVIDER_STATE_UNKNOWN for f in findings)
        has_warning = any(f.severity == SecuritySeverity.WARNING for f in findings)

        if has_critical:
            reasons = [f.explanation for f in findings if f.severity == SecuritySeverity.CRITICAL]
            return SecurityStatus.BLOCK, True, f"CRITICAL security violation: {'; '.join(reasons)}"

        if has_blocking:
            # Replay or capability abuse or expired auth
            reasons = [f.explanation for f in findings if f.severity == SecuritySeverity.BLOCKING]
            # Capability abuse or repeated replay triggers kill switch
            replay_or_cap = any(
                f.threat_code in (
                    SecurityThreatCode.REPLAY_DETECTED,
                    SecurityThreatCode.AGENT_CAPABILITY_VIOLATION,
                    SecurityThreatCode.STATE_DESYNC,
                )
                for f in findings
            )
            return SecurityStatus.BLOCK, replay_or_cap, (f"BLOCKING threat: {'; '.join(reasons)}" if replay_or_cap else None)

        if has_provider_unknown:
            return SecurityStatus.UNKNOWN, False, None

        if has_warning:
            return SecurityStatus.HOLD, False, None

        # Only INFO findings remain (e.g. deduplicated message)
        return SecurityStatus.CLEAR, False, None
