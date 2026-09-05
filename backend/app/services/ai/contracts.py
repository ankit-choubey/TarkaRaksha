"""
Contracts and intermediate DTOs for TarkaRaksha AI Services (T08).
All AI outputs are treated as untrusted inputs that must undergo Pydantic and domain validation.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.app.domain.models import ActionType


# --- AI Intermediate Data Transfer Objects (DTOs) ---

class AIIntentExtraction(BaseModel):
    """
    Structured representation extracted from natural-language user intent by AI.
    Intermediate format prior to authoritative IntentContract conversion.
    """
    sku: str = Field(..., description="Stock keeping unit or product code authorized by user")
    item_name: str = Field(..., description="Descriptive human-readable item name")
    quantity: int = Field(..., description="Number of units authorized")
    unit_price_minor: int = Field(..., description="Authorized unit price in minor currency units (e.g. paise)")
    max_total_minor: int = Field(..., description="Maximum authorized total expenditure in minor currency units")
    currency: str = Field(default="INR", description="ISO-4217 three-letter currency code")
    allowed_substitutions: List[str] = Field(default_factory=list, description="SKUs explicitly permitted for substitution")
    allow_partial: bool = Field(default=False, description="Whether partial fulfillment of quantity is permitted")
    max_retries: int = Field(default=3, description="Maximum permitted retry attempts")
    notes: Optional[str] = Field(default=None, description="Extracted non-functional observations")

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("quantity")
    @classmethod
    def validate_positive_quantity(cls, v: int) -> int:
        if isinstance(v, bool):
            raise TypeError("Boolean value forbidden for quantity")
        if v <= 0:
            raise ValueError("Quantity must be strictly positive")
        return v

    @field_validator("unit_price_minor", "max_total_minor")
    @classmethod
    def validate_non_negative_minor_units(cls, v: int) -> int:
        if isinstance(v, bool):
            raise TypeError("Boolean value forbidden for financial amounts")
        if v < 0:
            raise ValueError("Financial minor units cannot be negative")
        return v


class AIRecoverySuggestion(BaseModel):
    """
    Structured recovery suggestion proposed by the AI Recovery Agent in response to an MRDP.
    Strictly advisory. Never constitutes financial authorization.
    """
    proposed_action: ActionType = Field(..., description="Proposed corrective action (e.g. REFUND, VOID, NOTIFY)")
    suggested_amount_minor: Optional[int] = Field(default=None, description="Suggested compensation amount in minor units")
    currency: Optional[str] = Field(default="INR", description="Currency code for suggested amount")
    reasoning: str = Field(..., description="Technical rationale for the proposed recovery")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Model self-assessed confidence (informational only)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional non-authoritative parameters")

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("proposed_action", mode="before")
    @classmethod
    def validate_action_type(cls, v: Any) -> ActionType:
        if isinstance(v, ActionType):
            return v
        if isinstance(v, str):
            try:
                return ActionType(v.upper().strip())
            except ValueError:
                raise ValueError(f"Invalid ActionType '{v}'. Must be one of {[a.value for a in ActionType]}")
        raise TypeError(f"Expected string or ActionType, got {type(v).__name__}")

    @field_validator("suggested_amount_minor")
    @classmethod
    def validate_amount_minor(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if isinstance(v, bool):
                raise TypeError("Boolean forbidden for suggested amount")
            if v < 0:
                raise ValueError("Suggested amount cannot be negative")
        return v


# --- AI Exception Hierarchy ---

class AIError(Exception):
    """Base exception for all AI-related operations."""
    pass


class AIProviderError(AIError):
    """Exception raised when the underlying AI provider fails."""
    pass


class AITimeoutError(AIProviderError):
    """Exception raised when an AI request times out."""
    pass


class AIRateLimitError(AIProviderError):
    """Exception raised when rate limits are exceeded."""
    pass


class AIUnavailableError(AIProviderError):
    """Exception raised when the AI service is offline or unreachable."""
    pass


class StructuredOutputError(AIError):
    """Exception raised when the AI fails to produce valid structured JSON."""
    pass


class IntentParsingError(AIError):
    """Exception raised when intent parsing or domain validation fails."""
    pass


class UnsafeRecoveryProposalError(AIError):
    """Exception raised when an AI-generated recovery proposal violates domain safety invariants."""
    pass
