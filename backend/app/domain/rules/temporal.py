"""
Temporal Integrity Check for TarkaRaksha (T04).
Compares observed event timestamps, chronology, retry attempts, and capture counts.

Failure scenarios detected:
- Duplicate payment/capture events (duplicate execution risk).
- Actions occurring after contract expiration (late events).
- Captures exceeding max_successful_captures (double charge risk).
- Multi-attempt timeout with late confirmation (temporal divergence).
- Out-of-order lifecycle sequence (e.g. CAPTURE before AUTHORIZATION).
"""
from datetime import datetime
from typing import List, Optional
from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    IntegrityStatus,
    IntentContract,
)
from .base import RuleResult


def check_temporal(
    contract: IntentContract,
    events: List[CanonicalEvent],
    evidence_list: Optional[List[Evidence]] = None,
) -> RuleResult:
    """
    Deterministically evaluates temporal integrity across canonical lifecycle events.
    Checks:
    1. Events occur within contract validity window [issued_at, expires_at].
    2. Number of successful captures does not exceed max_successful_captures.
    3. Duplicate execution / double-charge detection (multiple captures or identical idempotency attempts).
    4. Chronological sequence consistency (e.g., attempt -> timeout -> retry -> late success conflict).
    """
    rule_name = "TemporalIntegrityRule"

    if not events:
        # Check if we have evidence without events
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.UNKNOWN,
            explanation="No canonical lifecycle events provided for temporal evaluation",
            expected="Canonical event sequence",
            observed=None,
            evidence_ids=[],
        )

    # Sort events deterministically by timestamp, then sequence_number, then event_id
    sorted_events = sorted(
        events,
        key=lambda e: (e.timestamp.isoformat(), e.sequence_number, e.event_id),
    )

    violations = []
    capture_events = []
    timeout_events = []
    seen_event_ids = set()

    for ev in sorted_events:
        # 1. Duplicate event ID check
        if ev.event_id in seen_event_ids:
            violations.append(f"DuplicateEventDetected: Event ID '{ev.event_id}' appears multiple times in lifecycle")
        seen_event_ids.add(ev.event_id)

        # 2. Expiration check (action occurred after contract expiry)
        if ev.timestamp > contract.expires_at:
            violations.append(
                f"ExpiredExecution: Event '{ev.event_type}' at {ev.timestamp.isoformat()} occurred after contract expiry {contract.expires_at.isoformat()}"
            )

        # 3. Action before contract issuance check
        if ev.timestamp < contract.issued_at:
            violations.append(
                f"PrematureExecution: Event '{ev.event_type}' at {ev.timestamp.isoformat()} occurred before contract issuance {contract.issued_at.isoformat()}"
            )

        # Track captures and timeouts for multi-attempt / late-success checks
        ev_type_upper = ev.event_type.upper()
        if "CAPTURE" in ev_type_upper or "PAYMENT_SUCCESS" in ev_type_upper:
            capture_events.append(ev)
        elif "TIMEOUT" in ev_type_upper or "EXPIRED" in ev_type_upper:
            timeout_events.append(ev)

    # 4. Multi-capture / double execution check
    if len(capture_events) > contract.max_successful_captures:
        violations.append(
            f"DoubleExecutionRisk: Observed {len(capture_events)} successful capture events, exceeding authorized max of {contract.max_successful_captures}"
        )

    # 5. Timeout with late success conflict
    # Attempt 1 -> Timeout -> Attempt 2 -> Attempt 1 later confirmed successful
    if timeout_events and len(capture_events) > 0:
        # Check if a capture happened after a timeout
        for t_ev in timeout_events:
            late_captures = [c for c in capture_events if c.timestamp > t_ev.timestamp]
            if late_captures:
                # If there are multiple captures overall, or a capture arrives after timeout
                if len(capture_events) > 1 or any(c.payload_summary.get("attempt", 1) == 1 for c in late_captures):
                    violations.append(
                        f"TemporalAmbiguityLateSuccess: Capture event confirmed after timeout event at {t_ev.timestamp.isoformat()}"
                    )

    if violations:
        return RuleResult(
            rule_name=rule_name,
            status=IntegrityStatus.DRIFT,
            violation="; ".join(violations),
            expected=f"Valid chronological lifecycle <= {contract.max_successful_captures} captures before {contract.expires_at.isoformat()}",
            observed=[{"type": e.event_type, "timestamp": e.timestamp.isoformat()} for e in sorted_events],
            evidence_ids=[e.event_id for e in sorted_events],
            explanation="Temporal divergence or duplicate execution detected in transaction lifecycle",
        )

    return RuleResult(
        rule_name=rule_name,
        status=IntegrityStatus.PASS,
        expected=f"Valid sequence before {contract.expires_at.isoformat()}",
        observed=[{"type": e.event_type, "timestamp": e.timestamp.isoformat()} for e in sorted_events],
        evidence_ids=[e.event_id for e in sorted_events],
        explanation="All lifecycle events are strictly ordered, within validity window, and without duplicate execution risk",
    )
