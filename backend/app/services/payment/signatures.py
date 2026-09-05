"""
Cryptographic Signature Verification for Payment and Webhook Integrations (T09).
Implements constant-time HMAC-SHA256 verification per official Razorpay specification.
Never prints, logs, or leaks secrets.
"""
import hashlib
import hmac
from typing import Union
from .contracts import PaymentSignatureError


def compute_payment_signature(order_id: str, payment_id: str, secret: str) -> str:
    """
    Computes the authoritative HMAC-SHA256 signature for client checkout completion:
    HMAC_SHA256(secret, order_id + "|" + payment_id)
    """
    if not order_id or not payment_id or not secret:
        raise ValueError("order_id, payment_id, and secret must all be non-empty strings")

    msg = f"{order_id}|{payment_id}".encode("utf-8")
    key = secret.encode("utf-8")
    return hmac.new(key=key, msg=msg, digestmod=hashlib.sha256).hexdigest()


def verify_payment_signature(
    order_id: str,
    payment_id: str,
    signature: str,
    secret: str,
) -> bool:
    """
    Verifies payment signature using constant-time comparison.
    Returns True if valid; raises PaymentSignatureError or returns False if invalid.
    """
    if not order_id or not payment_id or not signature or not secret:
        return False

    try:
        expected = compute_payment_signature(order_id, payment_id, secret)
        return hmac.compare_digest(expected.lower(), signature.strip().lower())
    except Exception:
        return False


def compute_webhook_signature(body: Union[str, bytes], secret: str) -> str:
    """
    Computes HMAC-SHA256 signature for a webhook payload body:
    HMAC_SHA256(secret, raw_body_bytes)
    """
    if not secret:
        raise ValueError("webhook secret must be non-empty")

    body_bytes = body.encode("utf-8") if isinstance(body, str) else body
    key = secret.encode("utf-8")
    return hmac.new(key=key, msg=body_bytes, digestmod=hashlib.sha256).hexdigest()


def verify_webhook_signature(
    body: Union[str, bytes],
    signature: str,
    secret: str,
) -> bool:
    """
    Verifies webhook signature against raw request body using constant-time comparison.
    Returns True if valid; returns False if invalid.
    """
    if not signature or not secret:
        return False

    try:
        expected = compute_webhook_signature(body, secret)
        return hmac.compare_digest(expected.lower(), signature.strip().lower())
    except Exception:
        return False
