"""OpenAI provider adapter for cloud model access."""

import time
from datetime import datetime

import httpx

from atlas.providers.base import (
    CompletionRequest,
    CompletionResponse,
    HealthStatus,
    ProviderAdapter,
    ProviderCapabilities,
    ProviderDownError,
    ProviderHealth,
    RateLimitError,
)


class OpenAIAdapter(ProviderAdapter):
    """
    Adapter for OpenAI API.

    Provides access to GPT-4, GPT-4o, and other OpenAI models.
    Requires API key (BYOK).
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self._client = httpx.AsyncClient(timeout=120.0)

        # Model capabilities
        self._capabilities: dict[str, ProviderCapabilities] = {
            "gpt-4o": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=16384,
                context_window=128000,
            ),
            "gpt-4o-mini": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=16384,
                context_window=128000,
            ),
            "gpt-4-turbo": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=4096,
                context_window=128000,
            ),
            "gpt-3.5-turbo": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=4096,
                context_window=16385,
            ),
        }

    @property
    def name(self) -> str:
        return "openai"

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with auth."""
        if not self.api_key:
            raise ProviderDownError(self.name, "OpenAI API key not configured")

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send completion request to OpenAI."""
        start_time = time.monotonic()

        payload: dict = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            )

            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 429:
                retry_after = response.headers.get("retry-after")
                raise RateLimitError(
                    self.name,
                    retry_after=int(retry_after) if retry_after else None,
                )

            response.raise_for_status()
            data = response.json()

            choice = data.get("choices", [{}])[0]

            return CompletionResponse(
                content=choice.get("message", {}).get("content", ""),
                model=data.get("model", request.model),
                provider=self.name,
                latency_ms=latency_ms,
                usage=data.get("usage"),
                finish_reason=choice.get("finish_reason"),
            )

        except httpx.ConnectError:
            raise ProviderDownError(self.name, "Cannot connect to OpenAI API")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderDownError(self.name, "Invalid OpenAI API key")
            raise ProviderDownError(self.name, f"OpenAI error: {e.response.status_code}")

    async def health_check(self) -> ProviderHealth:
        """Check OpenAI API availability."""
        if not self.api_key:
            return ProviderHealth(
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.utcnow(),
                error="API key not configured",
            )

        start_time = time.monotonic()

        try:
            # Use models endpoint for health check
            response = await self._client.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
            )
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                data = response.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                # Filter to chat models
                chat_models = [m for m in models if "gpt" in m.lower()]

                return ProviderHealth(
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                    last_check=datetime.utcnow(),
                    models_available=chat_models[:10],  # Top 10
                )

            return ProviderHealth(
                status=HealthStatus.DEGRADED,
                latency_ms=latency_ms,
                last_check=datetime.utcnow(),
                error=f"Unexpected status: {response.status_code}",
            )

        except httpx.ConnectError:
            return ProviderHealth(
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.utcnow(),
                error="Cannot connect to OpenAI API",
            )
        except Exception as e:
            return ProviderHealth(
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.utcnow(),
                error=str(e),
            )

    def get_capabilities(self, model: str) -> ProviderCapabilities:
        """Get capabilities for an OpenAI model."""
        return self._capabilities.get(model, ProviderCapabilities(strict_json=True))

    async def list_models(self) -> list[str]:
        """List available OpenAI models."""
        if not self.api_key:
            return []

        try:
            response = await self._client.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
            )
            if response.status_code == 200:
                data = response.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                return [m for m in models if "gpt" in m.lower()]
        except Exception:
            pass
        return []

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
