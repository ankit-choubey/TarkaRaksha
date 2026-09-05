"""
Money value object for TarkaRaksha.

Financial Safety Guarantees:
- Strict integer minor units (e.g., 50000 paise = ₹500.00).
- Explicit 3-letter uppercase ISO 4217 currency code.
- Strict rejection of floats, strings, booleans, and nulls.
- Immutable / frozen value object.
- Exact arithmetic operations preventing silent conversion or precision loss.
"""
from typing import Any
from pydantic import BaseModel, ConfigDict, field_validator


class Money(BaseModel):
    """
    Immutable representation of monetary value in integer minor units.
    """
    amount: int
    currency: str = "INR"

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("amount", mode="before")
    @classmethod
    def validate_strict_integer(cls, value: Any) -> int:
        # Python bool is a subclass of int: bool True == 1, False == 0.
        # We must explicitly reject booleans.
        if isinstance(value, bool):
            raise ValueError("Boolean value is strictly forbidden for Money.amount")
        
        # Explicitly reject float (even 50000.0)
        if isinstance(value, float):
            raise ValueError(f"Floating-point value {value} is strictly forbidden for Money.amount; use integer minor units")
        
        # Reject string coercion in case strict mode is bypassed
        if not isinstance(value, int):
            raise ValueError(f"Money.amount must be an integer, got {type(value).__name__}")
        
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError(f"Money.currency must be a string, got {type(value).__name__}")
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError(f"Invalid currency code '{value}': must be a 3-letter ISO-4217 code")
        return cleaned

    def __add__(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch in addition: {self.currency} != {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch in subtraction: {self.currency} != {other.currency}")
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, factor: Any) -> "Money":
        if isinstance(factor, bool) or not isinstance(factor, int):
            raise TypeError("Money can only be multiplied by a strict integer scalar")
        return Money(amount=self.amount * factor, currency=self.currency)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch in comparison: {self.currency} != {other.currency}")
        return self.amount < other.amount

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch in comparison: {self.currency} != {other.currency}")
        return self.amount <= other.amount

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch in comparison: {self.currency} != {other.currency}")
        return self.amount > other.amount

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch in comparison: {self.currency} != {other.currency}")
        return self.amount >= other.amount

    def __repr__(self) -> str:
        return f"Money({self.amount} {self.currency})"

    def format_major(self) -> str:
        """
        Format as human-readable major currency units (e.g. ₹500.00).
        For display / logging only; never used in internal calculations.
        """
        major = self.amount / 100.0
        return f"{self.currency} {major:.2f}"
