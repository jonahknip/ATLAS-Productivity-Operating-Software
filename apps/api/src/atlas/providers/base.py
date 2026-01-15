"""Base provider adapter interface and types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class HealthStatus(str, Enum):
    """Provider health status."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class ProviderCapabilities:
    """Capabilities of a provider/model combination."""

    strict_json: bool = False  # Can produce valid JSON reliably
    tool_calls: bool = False  # Supports function/tool calling
    streaming: bool = True  # Supports streaming responses
    max_tokens: int = 4096  # Maximum output tokens
    context_window: int = 8192  # Maximum context window


@dataclass
class ProviderHealth:
    """Current health status of a provider."""

    status: HealthStatus
    latency_ms: int | None = None
    last_check: datetime | None = None
    error: str | None = None
    models_available: list[str] | None = None


@dataclass
class CompletionRequest:
    """Request for model completion."""

    messages: list[dict[str, str]]
    model: str
    temperature: float = 0.7
    max_tokens: int = 2048
    json_mode: bool = False  # Request JSON output


@dataclass
class CompletionResponse:
    """Response from model completion."""

    content: str
    model: str
    provider: str
    usage: dict[str, int] | None = None  # tokens used
    latency_ms: int = 0
    finish_reason: str | None = None


class ProviderAdapter(ABC):
    """
    Abstract base class for provider adapters.

    Each provider (Ollama, OpenAI, etc.) implements this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'ollama', 'openai')."""
        ...

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """
        Send completion request to provider.

        Args:
            request: The completion request

        Returns:
            CompletionResponse with model output

        Raises:
            ProviderError on failure
        """
        ...

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """
        Check provider health and availability.

        Returns:
            ProviderHealth with current status
        """
        ...

    @abstractmethod
    def get_capabilities(self, model: str) -> ProviderCapabilities:
        """
        Get capabilities for a specific model.

        Args:
            model: Model identifier

        Returns:
            ProviderCapabilities for the model
        """
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        """
        List available models from this provider.

        Returns:
            List of model identifiers
        """
        ...

    async def close(self) -> None:
        """Close provider connections. Override in subclasses if needed."""
        pass


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, message: str, provider: str, recoverable: bool = True):
        super().__init__(message)
        self.provider = provider
        self.recoverable = recoverable


class RateLimitError(ProviderError):
    """Rate limit exceeded."""

    def __init__(self, provider: str, retry_after: int | None = None):
        super().__init__(f"Rate limit exceeded for {provider}", provider, recoverable=True)
        self.retry_after = retry_after


class ProviderDownError(ProviderError):
    """Provider is unavailable."""

    def __init__(self, provider: str, message: str = "Provider unavailable"):
        super().__init__(message, provider, recoverable=True)
