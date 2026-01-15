"""Anthropic provider adapter for Claude models."""

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


class AnthropicAdapter(ProviderAdapter):
    """
    Adapter for Anthropic Claude API.
    
    Supports Claude 3 models (Opus, Sonnet, Haiku).
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )

        # Model capabilities
        self._capabilities: dict[str, ProviderCapabilities] = {
            "claude-3-opus-20240229": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=4096,
                context_window=200000,
            ),
            "claude-3-sonnet-20240229": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=4096,
                context_window=200000,
            ),
            "claude-3-haiku-20240307": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=4096,
                context_window=200000,
            ),
            "claude-3-5-sonnet-20241022": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=8192,
                context_window=200000,
            ),
        }

    @property
    def name(self) -> str:
        return "anthropic"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send completion request to Anthropic."""
        start_time = time.monotonic()

        # Convert messages to Anthropic format
        system_message = None
        messages = []
        for msg in request.messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        payload = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        if system_message:
            payload["system"] = system_message

        try:
            response = await self._client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
            )

            if response.status_code == 429:
                raise RateLimitError(self.name)

            response.raise_for_status()
            data = response.json()

            latency_ms = int((time.monotonic() - start_time) * 1000)

            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")

            return CompletionResponse(
                content=content,
                model=request.model,
                provider=self.name,
                latency_ms=latency_ms,
                usage={
                    "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                    "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                },
                finish_reason=data.get("stop_reason"),
            )

        except httpx.ConnectError:
            raise ProviderDownError(self.name, "Cannot connect to Anthropic API")
        except httpx.HTTPStatusError as e:
            raise ProviderDownError(self.name, f"Anthropic error: {e.response.status_code}")

    async def health_check(self) -> ProviderHealth:
        """Check if Anthropic API is accessible."""
        start_time = time.monotonic()

        try:
            # Simple test request
            response = await self._client.post(
                "https://api.anthropic.com/v1/messages",
                json={
                    "model": "claude-3-haiku-20240307",
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 1,
                },
            )
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                return ProviderHealth(
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                    last_check=datetime.utcnow(),
                    models_available=list(self._capabilities.keys()),
                )
            elif response.status_code == 401:
                return ProviderHealth(
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=latency_ms,
                    last_check=datetime.utcnow(),
                    error="Invalid API key",
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
                error="Cannot connect to Anthropic API",
            )
        except Exception as e:
            return ProviderHealth(
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.utcnow(),
                error=str(e),
            )

    def get_capabilities(self, model: str) -> ProviderCapabilities:
        """Get capabilities for an Anthropic model."""
        return self._capabilities.get(model, ProviderCapabilities())

    async def list_models(self) -> list[str]:
        """List available Anthropic models."""
        return list(self._capabilities.keys())

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
