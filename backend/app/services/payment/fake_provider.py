"""
Deterministic In-Memory Fake Payment Provider for TarkaRaksha (T09).
Provides full test double capabilities without external network calls or secrets.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.app.domain.models import CanonicalEvent, Evidence, Money
from backend.app.domain.models.payment import (
    ProviderOrder,
    ProviderPayment,
    ProviderWebhookEvent,
)
from .contracts import (
    PaymentProvider,
    PaymentNotFoundError,
    PaymentSignatureError,
    WebhookValidationError,
)
from .signatures import (
    compute_payment_signature,
    compute_webhook_signature,
    verify_payment_signature,
    verify_webhook_signature,
)
from .normalization import (
    payment_to_evidence,
    webhook_to_event_and_evidence,
    parse_raw_webhook_payload,
)


class FakePaymentProvider(PaymentProvider):
    """
    In-memory, deterministic fake payment provider for unit testing.
    Supports configuring pre-seeded orders, payments, webhook events, and simulated errors.
    """

    def __init__(
        self,
        mock_secret: str = "mock_secret_key_123456",
        simulated_error: Optional[Exception] = None,
    ):
        self.mock_secret = mock_secret
        self.simulated_error = simulated_error
        self.orders: Dict[str, ProviderOrder] = {}
        self.payments: Dict[str, ProviderPayment] = {}
        self.order_payments: Dict[str, List[str]] = {}
        self.call_history: List[Dict[str, Any]] = []

    def set_simulated_error(self, error: Optional[Exception]) -> None:
        self.simulated_error = error

    def seed_order(self, order: ProviderOrder) -> None:
        self.orders[order.order_id] = order

    def seed_payment(self, payment: ProviderPayment) -> None:
        self.payments[payment.payment_id] = payment
        if payment.order_id:
            self.order_payments.setdefault(payment.order_id, []).append(payment.payment_id)

    def create_order(
        self,
        amount: Money,
        receipt: str,
        notes: Optional[Dict[str, str]] = None,
    ) -> ProviderOrder:
        self.call_history.append({
            "method": "create_order",
            "amount": amount,
            "receipt": receipt,
            "notes": notes,
        })
        if self.simulated_error:
            raise self.simulated_error

        order_id = f"order_mock_{hashlib.sha256(f'{receipt}:{amount.amount}'.encode('utf-8')).hexdigest()[:12]}"
        now = datetime.now(timezone.utc)
        order = ProviderOrder(
            order_id=order_id,
            amount=amount,
            currency=amount.currency,
            receipt=receipt,
            status="created",
            created_at=now,
            notes=notes or {},
            raw_reference=order_id,
        )
        self.orders[order_id] = order
        return order

    def fetch_payment(self, payment_id: str) -> ProviderPayment:
        self.call_history.append({"method": "fetch_payment", "payment_id": payment_id})
        if self.simulated_error:
            raise self.simulated_error

        if payment_id not in self.payments:
            raise PaymentNotFoundError(f"Payment '{payment_id}' not found")
        return self.payments[payment_id]

    def fetch_order_payments(self, order_id: str) -> List[ProviderPayment]:
        self.call_history.append({"method": "fetch_order_payments", "order_id": order_id})
        if self.simulated_error:
            raise self.simulated_error

        payment_ids = self.order_payments.get(order_id, [])
        return [self.payments[pid] for pid in payment_ids if pid in self.payments]

    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        self.call_history.append({
            "method": "verify_payment_signature",
            "order_id": order_id,
            "payment_id": payment_id,
            "signature": signature,
        })
        is_valid = verify_payment_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
            secret=self.mock_secret,
        )
        if not is_valid:
            raise PaymentSignatureError("Invalid checkout payment signature")
        return True

    def verify_webhook_signature(
        self,
        body: str,
        signature: str,
        webhook_secret: Optional[str] = None,
    ) -> bool:
        self.call_history.append({
            "method": "verify_webhook_signature",
            "signature": signature,
        })
        secret = webhook_secret or self.mock_secret
        is_valid = verify_webhook_signature(body=body, signature=signature, secret=secret)
        if not is_valid:
            raise PaymentSignatureError("Invalid webhook signature")
        return True

    def parse_webhook_payload(
        self,
        body: str,
        signature: str,
        webhook_secret: Optional[str] = None,
    ) -> ProviderWebhookEvent:
        self.verify_webhook_signature(body, signature, webhook_secret)
        try:
            data = json.loads(body)
        except Exception as exc:
            raise WebhookValidationError(f"Invalid JSON webhook: {exc}") from exc
        return parse_raw_webhook_payload(data)

    def normalize_payment_evidence(
        self,
        payment: ProviderPayment,
        intent_id: str,
    ) -> List[Evidence]:
        return payment_to_evidence(payment, intent_id)

    def normalize_webhook_event(
        self,
        event: ProviderWebhookEvent,
        intent_id: str,
    ) -> Tuple[CanonicalEvent, List[Evidence]]:
        return webhook_to_event_and_evidence(event, intent_id)
