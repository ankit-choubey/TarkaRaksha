"""
Unit tests for Money domain value object (T03 / Step 9 §9.6, §9.7).
Verifies strict integer minor units, float rejection, boolean rejection,
immutability, arithmetic operations, and serialization.
"""
import pytest
from pydantic import ValidationError
from backend.app.domain.models.money import Money


def test_money_valid_integer_minor_units():
    m = Money(amount=50000, currency="INR")
    assert m.amount == 50000
    assert m.currency == "INR"
    assert type(m.amount) is int
    assert not isinstance(m.amount, float)
    assert m.format_major() == "INR 500.00"


def test_money_boundary_values():
    m_49999 = Money(amount=49999, currency="INR")
    m_50000 = Money(amount=50000, currency="INR")
    m_50001 = Money(amount=50001, currency="INR")
    m_zero = Money(amount=0, currency="INR")
    m_huge = Money(amount=10_000_000_000, currency="INR")

    assert m_49999.amount == 49999
    assert m_50000.amount == 50000
    assert m_50001.amount == 50001
    assert m_zero.amount == 0
    assert m_huge.amount == 10_000_000_000


def test_money_rejects_floating_point():
    with pytest.raises(ValidationError) as excinfo:
        Money(amount=50000.5, currency="INR")
    assert "Floating-point value" in str(excinfo.value)

    with pytest.raises(ValidationError) as excinfo:
        Money(amount=50000.0, currency="INR")
    assert "Floating-point value" in str(excinfo.value)


def test_money_rejects_boolean():
    with pytest.raises(ValidationError) as excinfo:
        Money(amount=True, currency="INR")
    assert "Boolean value is strictly forbidden" in str(excinfo.value)

    with pytest.raises(ValidationError) as excinfo:
        Money(amount=False, currency="INR")
    assert "Boolean value is strictly forbidden" in str(excinfo.value)


def test_money_rejects_string():
    with pytest.raises(ValidationError):
        Money(amount="50000", currency="INR")


def test_money_currency_validation():
    # Valid uppercase 3-letter code
    m = Money(amount=100, currency="usd")
    assert m.currency == "USD"

    # Invalid currency codes
    with pytest.raises(ValidationError):
        Money(amount=100, currency="US")
    with pytest.raises(ValidationError):
        Money(amount=100, currency="USDT")
    with pytest.raises(ValidationError):
        Money(amount=100, currency="123")


def test_money_immutability():
    m = Money(amount=50000, currency="INR")
    with pytest.raises(ValidationError):
        m.amount = 60000


def test_money_arithmetic_addition():
    m1 = Money(amount=20000, currency="INR")
    m2 = Money(amount=30000, currency="INR")
    res = m1 + m2
    assert res.amount == 50000
    assert res.currency == "INR"
    assert type(res.amount) is int

    # Currency mismatch
    m_usd = Money(amount=100, currency="USD")
    with pytest.raises(ValueError, match="Currency mismatch"):
        _ = m1 + m_usd


def test_money_arithmetic_subtraction():
    m1 = Money(amount=50000, currency="INR")
    m2 = Money(amount=10000, currency="INR")
    res = m1 - m2
    assert res.amount == 40000
    assert res.currency == "INR"


def test_money_arithmetic_multiplication():
    m = Money(amount=1500, currency="INR")
    res = m * 3
    assert res.amount == 4500

    with pytest.raises(TypeError):
        _ = m * 2.5
    with pytest.raises(TypeError):
        _ = m * True


def test_money_comparisons():
    m1 = Money(amount=49999, currency="INR")
    m2 = Money(amount=50000, currency="INR")
    m3 = Money(amount=50000, currency="INR")

    assert m1 < m2
    assert m1 <= m2
    assert m2 > m1
    assert m2 >= m1
    assert m2 == m3


def test_money_serialization_roundtrip():
    original = Money(amount=50000, currency="INR")
    json_data = original.model_dump_json()
    reconstructed = Money.model_validate_json(json_data)
    assert reconstructed == original
    assert reconstructed.amount == 50000
    assert reconstructed.currency == "INR"
