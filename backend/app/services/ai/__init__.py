"""
AI Services package for TarkaRaksha (T08).
Provides Intent Parsing and Advisory Recovery Agent integrations with strict domain boundaries.
"""
from .contracts import (
    AIIntentExtraction,
    AIRecoverySuggestion,
    AIError,
    AIProviderError,
    AITimeoutError,
    AIRateLimitError,
    AIUnavailableError,
    StructuredOutputError,
    IntentParsingError,
    UnsafeRecoveryProposalError,
)
from .provider import (
    AIProvider,
    GroqAIProvider,
    FakeAIProvider,
)
from .intent_parser import (
    parse_intent,
    INTENT_PARSER_SYSTEM_PROMPT,
)

__all__ = [
    "AIIntentExtraction",
    "AIRecoverySuggestion",
    "AIError",
    "AIProviderError",
    "AITimeoutError",
    "AIRateLimitError",
    "AIUnavailableError",
    "StructuredOutputError",
    "IntentParsingError",
    "UnsafeRecoveryProposalError",
    "AIProvider",
    "GroqAIProvider",
    "FakeAIProvider",
    "parse_intent",
    "INTENT_PARSER_SYSTEM_PROMPT",
]
