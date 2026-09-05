"""
Payment Provider Contracts, Protocol, and Error Hierarchy for TarkaRaksha (T09).
Enforces the safety invariant:
Domain logic never depends directly on provider-specific response schemas.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from backend.app.domain.models import CanonicalEvent, Evidence, Money
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment, ProviderWebhookEvent


# --- Payment Provider Exception Hierarchy ---

class PaymentProviderError(Exception):
    """Base exception for all payment provider operations."""
    pass


class PaymentConfigurationError(PaymentProviderError):
    """Exception raised when payment provider credentials or configuration are missing or invalid."""
    pass


class PaymentAuthenticationError(PaymentProviderError):
    """Exception raised when gateway authentication fails."""
    pass


class PaymentNotFoundError(PaymentProviderError):
    """Exception raised when an order or payment resource is not found on the gateway."""
    pass


class PaymentTimeoutError(PaymentProviderError):
    """Exception raised when a gateway network request times out."""
    pass


class PaymentRateLimitError(PaymentProviderError):
    """Exception raised when gateway rate limits are exceeded (HTTP 429)."""
    pass


class PaymentSignatureError(PaymentProviderError):
    """Exception raised when signature verification fails for a payment or webhook."""
    pass


class PaymentInvalidRequestError(PaymentProviderError):
    """Exception raised when the gateway rejects request parameters (HTTP 400)."""
    pass


class PaymentServerError(PaymentProviderError):
    """Exception raised when the gateway encounters an internal server error (HTTP 5xx)."""
    pass


class WebhookValidationError(PaymentProviderError):
    """Exception raised when a webhook delivery cannot be verified or parsed."""
    pass


# --- Payment Provider Abstract Interface ---

class PaymentProvider(ABC):
    """
    Narrow provider-neutral interface between TarkaRaksha and external payment gateways.
    All financial amounts use integer minor units (Money).
    Never exposes provider-specific response dictionaries to the domain.
    """

    @abstractmethod
    def create_order(
        self,
        amount: Money,
        receipt: str,
        notes: Optional[Dict[str, str]] = None,
    ) -> ProviderOrder:
        """
        Creates an order on the payment gateway.
        Amount must be in integer minor units (e.g. paise for INR).
        """
        pass

    @abstractmethod
    def fetch_payment(self, payment_id: str) -> ProviderPayment:
        """
        Fetches authoritative payment details by payment ID.
        """
        pass

    @abstractmethod
    def fetch_order_payments(self, order_id: str) -> List[ProviderPayment]:
        """
        Fetches all payment attempts associated with a given order ID.
        """
        pass

    @abstractmethod
    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        """
        Verifies the cryptographic HMAC SHA-256 signature for client checkout completion.
        Returns True if signature is authentic, False or raises PaymentSignatureError if invalid.
        """
        pass

    @abstractmethod
    def verify_webhook_signature(
        self,
        body: str,
        signature: str,
        webhook_secret: Optional[str] = None,
    ) -> bool:
        """
        Verifies the cryptographic HMAC SHA-256 signature of an incoming webhook payload.
        """
        pass

    @abstractmethod
    def parse_webhook_payload(
        self,
        body: str,
        signature: str,
        webhook_secret: Optional[str] = None,
    ) -> ProviderWebhookEvent:
        """
        Verifies signature and parses raw webhook body into a ProviderWebhookEvent.
        """
        pass

    @abstractmethod
    def normalize_payment_evidence(
        self,
        payment: ProviderPayment,
        intent_id: str,
    ) -> List[Evidence]:
        """
        Translates a ProviderPayment into canonical Evidence records for deterministic verification.
        Uses EvidenceSource.RAZORPAY and EvidenceAuthority.AUTHORITATIVE.
        """
        pass

    @abstractmethod
    def normalize_webhook_event(
        self,
        event: ProviderWebhookEvent,
        intent_id: str,
    ) -> Tuple[CanonicalEvent, List[Evidence]]:
        """
        Translates a verified webhook event into a CanonicalEvent and corresponding Evidence records.
        """
        pass
