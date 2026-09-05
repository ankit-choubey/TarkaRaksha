"""
Normalization and Evidence Translation for Razorpay Gateway Entities (T09).
Maps raw gateway structures into clean domain Provider models and canonical T06 Evidence/Events.
Enforces the safety invariant:
The deterministic domain verifier never touches raw gateway payload dicts.
"""
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from backend.app.domain.models import (
    CanonicalEvent,
    Evidence,
    EvidenceAuthority,
    EvidenceSource,
    Money,
)
from backend.app.domain.models.payment import (
    ProviderOrder,
    ProviderPayment,
    ProviderWebhookEvent,
)
from .contracts import PaymentProviderError, WebhookValidationError


def parse_raw_order(payload: Dict[str, Any]) -> ProviderOrder:
    """
    Parses a raw Razorpay order payload into a provider-neutral ProviderOrder.
    Amount is strictly maintained in integer minor units (paise).
    """
    try:
        order_id = str(payload["id"])
        raw_amount = payload["amount"]
        if isinstance(raw_amount, bool) or not isinstance(raw_amount, int):
            raise TypeError(f"Order amount must be integer minor units, got {type(raw_amount).__name__}")
        if raw_amount < 0:
            raise ValueError("Order amount cannot be negative")

        currency = str(payload.get("currency", "INR")).upper()
        receipt = payload.get("receipt")
        status = str(payload.get("status", "created"))

        raw_created_at = payload.get("created_at")
        if isinstance(raw_created_at, (int, float)):
            created_at = datetime.fromtimestamp(raw_created_at, tz=timezone.utc)
        elif isinstance(raw_created_at, str):
            created_at = datetime.fromisoformat(raw_created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        elif isinstance(raw_created_at, datetime):
            created_at = raw_created_at if raw_created_at.tzinfo else raw_created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)

        notes = {str(k): str(v) for k, v in payload.get("notes", {}).items()} if isinstance(payload.get("notes"), dict) else {}

        return ProviderOrder(
            order_id=order_id,
            amount=Money(amount=raw_amount, currency=currency),
            currency=currency,
            receipt=str(receipt) if receipt else None,
            status=status,
            created_at=created_at,
            notes=notes,
            raw_reference=order_id,
        )
    except Exception as exc:
        raise PaymentProviderError(f"Failed to parse raw Razorpay order: {exc}") from exc


def parse_raw_payment(payload: Dict[str, Any]) -> ProviderPayment:
    """
    Parses a raw Razorpay payment payload into a provider-neutral ProviderPayment.
    """
    try:
        payment_id = str(payload["id"])
        raw_amount = payload["amount"]
        if isinstance(raw_amount, bool) or not isinstance(raw_amount, int):
            raise TypeError(f"Payment amount must be integer minor units, got {type(raw_amount).__name__}")
        if raw_amount < 0:
            raise ValueError("Payment amount cannot be negative")

        currency = str(payload.get("currency", "INR")).upper()
        status = str(payload.get("status", "unknown")).lower()
        order_id = payload.get("order_id")
        method = payload.get("method")
        captured = bool(payload.get("captured", False))

        raw_created_at = payload.get("created_at")
        if isinstance(raw_created_at, (int, float)):
            created_at = datetime.fromtimestamp(raw_created_at, tz=timezone.utc)
        elif isinstance(raw_created_at, str):
            created_at = datetime.fromisoformat(raw_created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        elif isinstance(raw_created_at, datetime):
            created_at = raw_created_at if raw_created_at.tzinfo else raw_created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)

        error_code = payload.get("error_code")
        error_desc = payload.get("error_description")
        notes = {str(k): str(v) for k, v in payload.get("notes", {}).items()} if isinstance(payload.get("notes"), dict) else {}

        return ProviderPayment(
            payment_id=payment_id,
            order_id=str(order_id) if order_id else None,
            amount=Money(amount=raw_amount, currency=currency),
            currency=currency,
            status=status,
            method=str(method) if method else None,
            captured=captured,
            created_at=created_at,
            error_code=str(error_code) if error_code else None,
            error_description=str(error_desc) if error_desc else None,
            notes=notes,
        )
    except Exception as exc:
        raise PaymentProviderError(f"Failed to parse raw Razorpay payment: {exc}") from exc


def parse_raw_webhook_payload(payload: Dict[str, Any]) -> ProviderWebhookEvent:
    """
    Parses an authenticated raw Razorpay webhook payload into a ProviderWebhookEvent.
    """
    try:
        event_type = str(payload["event"])
        raw_created_at = payload.get("created_at")
        if isinstance(raw_created_at, (int, float)):
            created_at = datetime.fromtimestamp(raw_created_at, tz=timezone.utc)
        elif isinstance(raw_created_at, str):
            created_at = datetime.fromisoformat(raw_created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)

        # Webhook event ID (Razorpay includes it as payload id or x-razorpay-event-id; synthesize stable fallback if missing)
        event_id = payload.get("id") or payload.get("event_id")
        if not event_id:
            # Deterministic hash of event + timestamp + account_id
            synth_input = f"{event_type}:{created_at.isoformat()}:{payload.get('account_id', '')}"
            event_id = f"evt_{hashlib.sha256(synth_input.encode('utf-8')).hexdigest()[:16]}"
        event_id = str(event_id)

        parsed_payment: Optional[ProviderPayment] = None
        parsed_order: Optional[ProviderOrder] = None

        raw_payload_section = payload.get("payload", {})
        if isinstance(raw_payload_section, dict):
            # Extract payment entity
            payment_entity = raw_payload_section.get("payment", {}).get("entity")
            if isinstance(payment_entity, dict):
                parsed_payment = parse_raw_payment(payment_entity)

            # Extract order entity
            order_entity = raw_payload_section.get("order", {}).get("entity")
            if isinstance(order_entity, dict):
                parsed_order = parse_raw_order(order_entity)

        return ProviderWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payment=parsed_payment,
            order=parsed_order,
            created_at=created_at,
            raw_payload=payload,
        )
    except Exception as exc:
        raise WebhookValidationError(f"Malformed webhook payload structure: {exc}") from exc


def payment_to_evidence(
    payment: ProviderPayment,
    intent_id: str,
) -> List[Evidence]:
    """
    Translates a ProviderPayment into canonical Evidence records for deterministic verification.
    Follows T06 evidence taxonomy with EvidenceSource.RAZORPAY and EvidenceAuthority.AUTHORITATIVE.
    """
    records: List[Evidence] = []
    base_id = payment.payment_id

    # 1. Total Amount Evidence (Crucial for Economic rule)
    records.append(
        Evidence(
            evidence_id=f"ev_rzp_{base_id}_amount",
            intent_id=intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="total_amount",
            field_value=payment.amount,
            observed_at=payment.created_at,
            raw_reference=payment.payment_id,
        )
    )

    # 2. Currency Evidence
    records.append(
        Evidence(
            evidence_id=f"ev_rzp_{base_id}_curr",
            intent_id=intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="currency",
            field_value=payment.currency,
            observed_at=payment.created_at,
            raw_reference=payment.payment_id,
        )
    )

    # 3. Payment Status Evidence
    records.append(
        Evidence(
            evidence_id=f"ev_rzp_{base_id}_status",
            intent_id=intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="payment_status",
            field_value=payment.status,
            observed_at=payment.created_at,
            raw_reference=payment.payment_id,
        )
    )

    # 4. Capture Status Evidence
    records.append(
        Evidence(
            evidence_id=f"ev_rzp_{base_id}_capture",
            intent_id=intent_id,
            source=EvidenceSource.RAZORPAY,
            authority=EvidenceAuthority.AUTHORITATIVE,
            field_name="capture_status",
            field_value=payment.captured,
            observed_at=payment.created_at,
            raw_reference=payment.payment_id,
        )
    )

    # 5. Order Reference Evidence if available
    if payment.order_id:
        records.append(
            Evidence(
                evidence_id=f"ev_rzp_{base_id}_order",
                intent_id=intent_id,
                source=EvidenceSource.RAZORPAY,
                authority=EvidenceAuthority.AUTHORITATIVE,
                field_name="order_id",
                field_value=payment.order_id,
                observed_at=payment.created_at,
                raw_reference=payment.payment_id,
            )
        )

    return records


def webhook_to_event_and_evidence(
    event: ProviderWebhookEvent,
    intent_id: str,
) -> Tuple[CanonicalEvent, List[Evidence]]:
    """
    Translates an authenticated ProviderWebhookEvent into a CanonicalEvent and Evidence records.
    Preserves event ordering and identity without synthetic falsification.
    """
    payload_summary = {
        "event_id": event.event_id,
        "event_type": event.event_type,
    }
    if event.payment:
        payload_summary["payment_id"] = event.payment.payment_id
        payload_summary["amount"] = event.payment.amount.amount
        payload_summary["currency"] = event.payment.amount.currency
        payload_summary["status"] = event.payment.status
        payload_summary["captured"] = event.payment.captured
    if event.order:
        payload_summary["order_id"] = event.order.order_id

    canonical_event = CanonicalEvent(
        event_id=event.event_id,
        intent_id=intent_id,
        event_type=event.event_type,
        source=EvidenceSource.RAZORPAY,
        authority=EvidenceAuthority.AUTHORITATIVE,
        occurred_at=event.created_at,
        payload=payload_summary,
    )

    evidence_records: List[Evidence] = []
    if event.payment:
        evidence_records = payment_to_evidence(event.payment, intent_id)

    return canonical_event, evidence_records
