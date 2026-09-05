"""
Payment services package for TarkaRaksha (T09).
Provides provider-neutral payment abstractions, Razorpay adapter, and deterministic test double.
"""
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
from .signatures import (
    compute_payment_signature,
    verify_payment_signature,
    compute_webhook_signature,
    verify_webhook_signature,
)
from .normalization import (
    parse_raw_order,
    parse_raw_payment,
    parse_raw_webhook_payload,
    payment_to_evidence,
    webhook_to_event_and_evidence,
)

__all__ = [
    "ProviderOrder",
    "ProviderPayment",
    "ProviderWebhookEvent",
    "PaymentProvider",
    "PaymentProviderError",
    "PaymentConfigurationError",
    "PaymentAuthenticationError",
    "PaymentNotFoundError",
    "PaymentTimeoutError",
    "PaymentRateLimitError",
    "PaymentSignatureError",
    "PaymentInvalidRequestError",
    "PaymentServerError",
    "WebhookValidationError",
    "compute_payment_signature",
    "verify_payment_signature",
    "compute_webhook_signature",
    "verify_webhook_signature",
    "parse_raw_order",
    "parse_raw_payment",
    "parse_raw_webhook_payload",
    "payment_to_evidence",
    "webhook_to_event_and_evidence",
]
