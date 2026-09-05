"""
Narrow AI Provider interface and concrete implementations for TarkaRaksha.
Provides abstract AIProvider, GroqAIProvider, and FakeAIProvider.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import json
import httpx

from backend.app.core.config import settings
from .contracts import (
    AIProviderError,
    AITimeoutError,
    AIRateLimitError,
    AIUnavailableError,
)


class AIProvider(ABC):
    """
    Abstract interface defining the narrow boundary between TarkaRaksha domain services
    and external AI inference providers.
    """
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        """
        Generate raw text/JSON completion from the model.
        Returns the raw response string without parsing.
        """
        pass


class GroqAIProvider(AIProvider):
    """
    Concrete AI provider backed by the Groq SDK.
    Translates SDK/HTTP exceptions into canonical TarkaRaksha AI exceptions.
    Never prints, logs, or leaks the API key.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.timeout_seconds = timeout_seconds or settings.groq_timeout_seconds
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key or not self.api_key.strip():
                raise AIUnavailableError("GROQ_API_KEY is not configured or is empty")
            try:
                import groq
                self._client = groq.Client(
                    api_key=self.api_key,
                    timeout=httpx.Timeout(self.timeout_seconds),
                )
            except Exception as e:
                raise AIUnavailableError(f"Failed to initialize Groq client: {e}")
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        client = self._get_client()
        target_model = model or self.model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        try:
            response = client.chat.completions.create(**kwargs)
            if not response.choices or not response.choices[0].message:
                raise AIProviderError("Groq returned empty response choices")
            content = response.choices[0].message.content
            if content is None:
                raise AIProviderError("Groq returned null response content")
            return content
        except Exception as exc:
            self._handle_groq_exception(exc)

    def _handle_groq_exception(self, exc: Exception) -> None:
        exc_str = str(exc).lower()
        if "timeout" in exc_str or "timed out" in exc_str:
            raise AITimeoutError(f"Groq request timed out: {exc}") from exc
        elif "rate_limit" in exc_str or "429" in exc_str:
            raise AIRateLimitError(f"Groq rate limit exceeded: {exc}") from exc
        elif "connection" in exc_str or "unavailable" in exc_str or "503" in exc_str:
            raise AIUnavailableError(f"Groq service unavailable: {exc}") from exc
        else:
            raise AIProviderError(f"Groq API error: {exc}") from exc


class FakeAIProvider(AIProvider):
    """
    Deterministic fake AI provider for local, isolated, repeatable testing.
    Supports injecting sequences of pre-configured responses or exceptions.
    Zero external network calls.
    """
    def __init__(
        self,
        responses: Optional[List[Union[str, Exception]]] = None,
        default_response: str = "{}",
    ):
        self._responses: List[Union[str, Exception]] = list(responses) if responses else []
        self._default_response = default_response
        self.call_count: int = 0
        self.call_history: List[Dict[str, Any]] = []

    def add_response(self, response: Union[str, Exception]) -> None:
        self._responses.append(response)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        self.call_count += 1
        self.call_history.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "response_format": response_format,
            "model": model,
            "temperature": temperature,
        })

        if self._responses:
            item = self._responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return self._default_response
