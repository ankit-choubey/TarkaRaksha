"""
Razorpay Payment Gateway Adapter for TarkaRaksha (T09).
Encapsulates all communication with the official Razorpay SDK and translates
gateway-specific responses into provider-neutral domain models and canonical evidence.
Never leaks credentials, authorization keys, or raw provider payload structures.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import settings
from backend.app.domain.models import CanonicalEvent, Evidence, Money
from backend.app.domain.models.payment import (
    ProviderOrder,
    ProviderPayment,
    ProviderWebhookEvent,
)
from .contracts import (
    PaymentProvider,
    PaymentProviderError,
    PaymentConfigurationError,
    PaymentAuthenticationError,
    PaymentNotFoundError,
    PaymentTimeoutError,
    PaymentRateLimitError,
    PaymentSignatureError,
    PaymentInvalidRequestError,
    PaymentServerError,
    WebhookValidationError,
)
from .signatures import verify_payment_signature, verify_webhook_signature
from .normalization import (
    parse_raw_order,
    parse_raw_payment,
    parse_raw_webhook_payload,
    payment_to_evidence,
    webhook_to_event_and_evidence,
)

logger = logging.getLogger(__name__)

_UNSET = object()


class RazorpayAdapter(PaymentProvider):
    """
    Concrete adapter connecting TarkaRaksha to the Razorpay Payments API.
    All financial amounts must be integer minor units (paise for INR).
    Never makes domain integrity decisions or overrides deterministic rules.
    """

    def __init__(
        self,
        key_id: Any = _UNSET,
        key_secret: Any = _UNSET,
        timeout_seconds: float = 30.0,
    ):
        self.key_id = settings.razorpay_key_id if key_id is _UNSET else (key_id or "")
        self.key_secret = settings.razorpay_key_secret if key_secret is _UNSET else (key_secret or "")
        self.timeout_seconds = timeout_seconds
        self._client = None

    def _get_client(self):
        """Initializes and returns the authenticated Razorpay SDK client."""
        if self._client is None:
            if not self.key_id or not self.key_secret:
                raise PaymentConfigurationError(
                    "Razorpay credentials missing: RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be configured"
                )
            try:
                import razorpay
                self._client = razorpay.Client(auth=(self.key_id, self.key_secret))
                self._client.set_app_details({
                    "title": "TarkaRaksha Control Plane",
                    "version": "1.0.0",
                })
            except Exception as exc:
                raise PaymentConfigurationError(f"Failed to initialize Razorpay client: {exc}") from exc
        return self._client

    def create_order(
        self,
        amount: Money,
        receipt: str,
        notes: Optional[Dict[str, str]] = None,
    ) -> ProviderOrder:
        """
        Creates an order on Razorpay.
        Amount must be integer minor units (e.g. paise: 50000 INR = 5000000 paise).
        """
        if amount.amount < 100:  # Razorpay minimum order amount is ₹1.00 (100 paise)
            raise PaymentInvalidRequestError(f"Razorpay order amount {amount.amount} is below minimum allowed (100 minor units)")

        client = self._get_client()
        order_data: Dict[str, Any] = {
            "amount": amount.amount,
            "currency": amount.currency.upper(),
            "receipt": receipt,
            "notes": notes or {},
            "payment_capture": 1,  # Standard auto-capture preference
        }

        try:
            raw_response = client.order.create(data=order_data)
            return parse_raw_order(raw_response)
        except Exception as exc:
            self._handle_razorpay_exception(exc, context="create_order")

    def fetch_payment(self, payment_id: str) -> ProviderPayment:
        """
        Fetches authoritative payment record from Razorpay API.
        """
        if not payment_id or not payment_id.strip():
            raise PaymentInvalidRequestError("payment_id cannot be empty")

        client = self._get_client()
        try:
            raw_response = client.payment.fetch(payment_id.strip())
            return parse_raw_payment(raw_response)
        except Exception as exc:
            self._handle_razorpay_exception(exc, context=f"fetch_payment({payment_id})")

    def fetch_order_payments(self, order_id: str) -> List[ProviderPayment]:
        """
        Fetches all payment attempts associated with a given order.
        """
        if not order_id or not order_id.strip():
            raise PaymentInvalidRequestError("order_id cannot be empty")

        client = self._get_client()
        try:
            raw_response = client.order.payments(order_id.strip())
            items = raw_response.get("items", []) if isinstance(raw_response, dict) else raw_response
            return [parse_raw_payment(item) for item in items]
        except Exception as exc:
            self._handle_razorpay_exception(exc, context=f"fetch_order_payments({order_id})")

    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        """
        Verifies the cryptographic HMAC SHA-256 checkout completion signature.
        """
        if not self.key_secret:
            raise PaymentConfigurationError("RAZORPAY_KEY_SECRET is required to verify signatures")

        is_valid = verify_payment_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
            secret=self.key_secret,
        )
        if not is_valid:
            raise PaymentSignatureError("Razorpay checkout payment signature verification failed")
        return True

    def verify_webhook_signature(
        self,
        body: str,
        signature: str,
        webhook_secret: Optional[str] = None,
    ) -> bool:
        """
        Verifies incoming webhook HMAC-SHA256 signature against request body.
        """
        secret = webhook_secret or self.key_secret
        if not secret:
            raise PaymentConfigurationError("Webhook secret is required to verify webhook signature")

        is_valid = verify_webhook_signature(body=body, signature=signature, secret=secret)
        if not is_valid:
            raise PaymentSignatureError("Razorpay webhook signature verification failed")
        return True

    def parse_webhook_payload(
        self,
        body: str,
        signature: str,
        webhook_secret: Optional[str] = None,
    ) -> ProviderWebhookEvent:
        """
        Verifies signature and parses incoming webhook payload into ProviderWebhookEvent.
        """
        self.verify_webhook_signature(body, signature, webhook_secret)
        try:
            payload_dict = json.loads(body)
        except json.JSONDecodeError as jde:
            raise WebhookValidationError(f"Webhook payload is not valid JSON: {jde}") from jde

        return parse_raw_webhook_payload(payload_dict)

    def normalize_payment_evidence(
        self,
        payment: ProviderPayment,
        intent_id: str,
    ) -> List[Evidence]:
        """
        Translates ProviderPayment into canonical Evidence records for deterministic verification.
        """
        return payment_to_evidence(payment, intent_id)

    def normalize_webhook_event(
        self,
        event: ProviderWebhookEvent,
        intent_id: str,
    ) -> Tuple[CanonicalEvent, List[Evidence]]:
        """
        Translates ProviderWebhookEvent into CanonicalEvent and corresponding Evidence.
        """
        return webhook_to_event_and_evidence(event, intent_id)

    def _handle_razorpay_exception(self, exc: Exception, context: str) -> None:
        """Translates SDK and HTTP errors into canonical TarkaRaksha payment errors."""
        msg = str(exc)
        msg_lower = msg.lower()

        # Check for authentication / credentials failure
        if "401" in msg or "unauthorized" in msg_lower or "authentication" in msg_lower:
            raise PaymentAuthenticationError(f"Razorpay authentication failed during {context}: {msg}") from exc

        # Check for resource not found
        if "404" in msg or "not_found" in msg_lower or "not found" in msg_lower:
            raise PaymentNotFoundError(f"Razorpay resource not found during {context}: {msg}") from exc

        # Check for rate limits
        if "429" in msg or "rate_limit" in msg_lower:
            raise PaymentRateLimitError(f"Razorpay rate limit exceeded during {context}: {msg}") from exc

        # Check for timeout / network issues
        if "timeout" in msg_lower or "timed out" in msg_lower:
            raise PaymentTimeoutError(f"Razorpay network timeout during {context}: {msg}") from exc

        # Check for invalid request / bad request
        if "badrequest" in type(exc).__name__.lower() or "400" in msg:
            raise PaymentInvalidRequestError(f"Razorpay bad request during {context}: {msg}") from exc

        # Check for server errors
        if "servererror" in type(exc).__name__.lower() or "500" in msg or "502" in msg or "503" in msg:
            raise PaymentServerError(f"Razorpay server error during {context}: {msg}") from exc

        raise PaymentProviderError(f"Razorpay operation failed during {context}: {msg}") from exc
