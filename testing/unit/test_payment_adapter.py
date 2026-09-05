"""
Unit Test Suite for TarkaRaksha Payment Adapter (T09).
Testing reference: brain/TarkaRaksha_TESTING.md §9.37–§9.41.

Covers:
- Order creation: integer minor units, INR amount mapping, minimum amount guard
- Payment retrieval: known response into canonical ProviderPayment
- Order payments: retrieval of payment collections
- Signature verification: valid signature, invalid signature, wrong secret, tampered data
- Error matrix: 401 auth failure, 404 not found, 429 rate limit, 500 server error, timeout
- Malformed responses: rejection of non-integer financial amounts, invalid types
"""
from datetime import datetime, timezone
import pytest

from backend.app.domain.models import Money
from backend.app.domain.models.payment import ProviderOrder, ProviderPayment
from backend.app.services.payment import (
    FakePaymentProvider,
    PaymentAuthenticationError,
    PaymentConfigurationError,
    PaymentInvalidRequestError,
    PaymentNotFoundError,
    PaymentRateLimitError,
    PaymentServerError,
    PaymentSignatureError,
    PaymentTimeoutError,
    RazorpayAdapter,
    compute_payment_signature,
    compute_webhook_signature,
    parse_raw_order,
    parse_raw_payment,
    verify_payment_signature,
    verify_webhook_signature,
)


# ==============================================================================
# 1. ORDER CREATION AND NORMALIZATION TESTS
# ==============================================================================

def test_order_creation_with_integer_minor_units():
    """₹50,000 is represented strictly as 5,000,000 paise without floating-point conversion."""
    fake = FakePaymentProvider()
    amount = Money(amount=5000000, currency="INR")
    order = fake.create_order(amount=amount, receipt="rcpt_test_01", notes={"item": "SERVER-256GB"})

    assert isinstance(order, ProviderOrder)
    assert order.amount == amount
    assert order.amount.amount == 5000000
    assert order.currency == "INR"
    assert order.receipt == "rcpt_test_01"
    assert order.notes.get("item") == "SERVER-256GB"


def test_parse_raw_razorpay_order():
    """Valid raw Razorpay order JSON structure parses correctly into ProviderOrder."""
    raw_payload = {
        "id": "order_EKwxwAgItmmXdp",
        "entity": "order",
        "amount": 5000000,
        "amount_paid": 0,
        "amount_due": 5000000,
        "currency": "INR",
        "receipt": "rcpt_srv_1",
        "status": "created",
        "attempts": 0,
        "notes": {"sku": "SERVER-256GB"},
        "created_at": 1586940798,
    }
    order = parse_raw_order(raw_payload)

    assert order.order_id == "order_EKwxwAgItmmXdp"
    assert order.amount == Money(amount=5000000, currency="INR")
    assert order.status == "created"
    assert order.created_at.year == 2020


def test_order_rejection_for_float_amount():
    """Float amounts in raw order payloads are rejected by strict integer minor unit checks."""
    raw_payload = {
        "id": "order_float_invalid",
        "amount": 50000.50,  # Invalid float!
        "currency": "INR",
        "status": "created",
    }
    with pytest.raises(Exception):
        parse_raw_order(raw_payload)


def test_razorpay_minimum_amount_guard():
    """Orders below Razorpay minimum ₹1.00 (100 paise) are rejected."""
    adapter = RazorpayAdapter(key_id="mock_id", key_secret="mock_secret")
    with pytest.raises(PaymentInvalidRequestError, match="below minimum allowed"):
        adapter.create_order(Money(amount=50, currency="INR"), receipt="rcpt_low")


# ==============================================================================
# 2. PAYMENT RETRIEVAL AND NORMALIZATION TESTS
# ==============================================================================

def test_parse_raw_razorpay_payment():
    """Valid raw Razorpay payment JSON structure parses correctly into ProviderPayment."""
    raw_payload = {
        "id": "pay_29Ae30Xdu9Rf5V",
        "entity": "payment",
        "amount": 5500000,
        "currency": "INR",
        "status": "captured",
        "order_id": "order_EKwxwAgItmmXdp",
        "method": "card",
        "captured": True,
        "created_at": 1586940840,
        "notes": {},
    }
    payment = parse_raw_payment(raw_payload)

    assert isinstance(payment, ProviderPayment)
    assert payment.payment_id == "pay_29Ae30Xdu9Rf5V"
    assert payment.order_id == "order_EKwxwAgItmmXdp"
    assert payment.amount == Money(amount=5500000, currency="INR")
    assert payment.captured is True
    assert payment.status == "captured"


def test_fetch_payment_and_order_payments_in_fake_provider():
    """FakePaymentProvider retrieves seeded payments and order payments correctly."""
    fake = FakePaymentProvider()
    now = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    payment = ProviderPayment(
        payment_id="pay_seeded_01",
        order_id="order_seeded_01",
        amount=Money(amount=5000000, currency="INR"),
        currency="INR",
        status="captured",
        captured=True,
        created_at=now,
    )
    fake.seed_payment(payment)

    fetched = fake.fetch_payment("pay_seeded_01")
    assert fetched.payment_id == "pay_seeded_01"
    assert fetched.amount.amount == 5000000

    order_payments = fake.fetch_order_payments("order_seeded_01")
    assert len(order_payments) == 1
    assert order_payments[0].payment_id == "pay_seeded_01"


def test_fetch_payment_not_found_raises_error():
    """Fetching an unseeded or non-existent payment raises PaymentNotFoundError."""
    fake = FakePaymentProvider()
    with pytest.raises(PaymentNotFoundError, match="not found"):
        fake.fetch_payment("pay_non_existent")


# ==============================================================================
# 3. CRYPTOGRAPHIC SIGNATURE VERIFICATION TESTS
# ==============================================================================

def test_payment_signature_verification_success():
    """Valid HMAC-SHA256 signature generated with matching secret verifies successfully."""
    secret = "rzp_test_secret_987654321"
    order_id = "order_O4j5k6l7m8n9"
    payment_id = "pay_P1q2r3s4t5u6"

    signature = compute_payment_signature(order_id, payment_id, secret)
    assert verify_payment_signature(order_id, payment_id, signature, secret) is True


def test_payment_signature_verification_failure_cases():
    """Tampered order, payment, wrong secret, or invalid signature fails verification."""
    secret = "rzp_test_secret_987654321"
    order_id = "order_O4j5k6l7m8n9"
    payment_id = "pay_P1q2r3s4t5u6"
    valid_sig = compute_payment_signature(order_id, payment_id, secret)

    # 1. Wrong secret
    assert verify_payment_signature(order_id, payment_id, valid_sig, "wrong_secret") is False

    # 2. Tampered order ID
    assert verify_payment_signature("order_tampered", payment_id, valid_sig, secret) is False

    # 3. Tampered payment ID
    assert verify_payment_signature(order_id, "pay_tampered", valid_sig, secret) is False

    # 4. Invalid signature string
    assert verify_payment_signature(order_id, payment_id, "invalid_sig_hex", secret) is False

    # 5. Empty fields
    assert verify_payment_signature("", payment_id, valid_sig, secret) is False


def test_webhook_signature_verification():
    """Webhook body HMAC-SHA256 signature verifies correctly and fails on payload tampering."""
    secret = "wh_secret_xyz123"
    body = '{"event": "payment.captured", "id": "evt_001"}'
    valid_sig = compute_webhook_signature(body, secret)

    assert verify_webhook_signature(body, valid_sig, secret) is True
    # Tampered body fails
    assert verify_webhook_signature(body + " ", valid_sig, secret) is False
    # Wrong secret fails
    assert verify_webhook_signature(body, valid_sig, "wrong_wh_secret") is False


# ==============================================================================
# 4. ERROR HANDLING AND FAILURE MATRIX TESTS
# ==============================================================================

def test_razorpay_adapter_exception_translation():
    """RazorpayAdapter translates various SDK exceptions into explicit domain payment exceptions."""
    adapter = RazorpayAdapter(key_id="mock_id", key_secret="mock_secret")

    # Authentication failure (401)
    with pytest.raises(PaymentAuthenticationError):
        adapter._handle_razorpay_exception(Exception("401 Unauthorized: Invalid API key"), "test")

    # Resource not found (404)
    with pytest.raises(PaymentNotFoundError):
        adapter._handle_razorpay_exception(Exception("404 Not Found: Entity does not exist"), "test")

    # Rate limit (429)
    with pytest.raises(PaymentRateLimitError):
        adapter._handle_razorpay_exception(Exception("429 Too Many Requests"), "test")

    # Timeout
    with pytest.raises(PaymentTimeoutError):
        adapter._handle_razorpay_exception(Exception("Request timed out after 30s"), "test")

    # Server error (500)
    with pytest.raises(PaymentServerError):
        adapter._handle_razorpay_exception(Exception("500 Internal Server Error"), "test")


def test_razorpay_missing_credentials_configuration_error():
    """Attempting adapter operations without credentials raises PaymentConfigurationError."""
    adapter = RazorpayAdapter(key_id=None, key_secret=None)
    with pytest.raises(PaymentConfigurationError, match="Razorpay credentials missing"):
        adapter.create_order(Money(amount=5000000, currency="INR"), receipt="rcpt_1")
