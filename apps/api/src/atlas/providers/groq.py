"""Groq provider adapter for ultra-fast inference."""

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


class GroqAdapter(ProviderAdapter):
    """
    Adapter for Groq API.
    
    Groq provides ultra-fast inference for open models like
    Llama, Mixtral, and Gemma.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        # Model capabilities
        self._capabilities: dict[str, ProviderCapabilities] = {
            "llama-3.3-70b-versatile": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=8192,
                context_window=128000,
            ),
            "llama-3.1-8b-instant": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=8192,
                context_window=128000,
            ),
            "llama3-70b-8192": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=8192,
                context_window=8192,
            ),
            "llama3-8b-8192": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=8192,
                context_window=8192,
            ),
            "mixtral-8x7b-32768": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=32768,
                context_window=32768,
            ),
            "gemma2-9b-it": ProviderCapabilities(
                strict_json=True,
                tool_calls=True,
                max_tokens=8192,
                context_window=8192,
            ),
        }

    @property
    def name(self) -> str:
        return "groq"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send completion request to Groq."""
        start_time = time.monotonic()

        payload = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = await self._client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
            )

            if response.status_code == 429:
                raise RateLimitError(self.name)

            response.raise_for_status()
            data = response.json()

            latency_ms = int((time.monotonic() - start_time) * 1000)

            return CompletionResponse(
                content=data["choices"][0]["message"]["content"],
                model=request.model,
                provider=self.name,
                latency_ms=latency_ms,
                usage={
                    "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                    "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                },
                finish_reason=data["choices"][0].get("finish_reason"),
            )

        except httpx.ConnectError:
            raise ProviderDownError(self.name, "Cannot connect to Groq API")
        except httpx.HTTPStatusError as e:
            raise ProviderDownError(self.name, f"Groq error: {e.response.status_code}")

    async def health_check(self) -> ProviderHealth:
        """Check if Groq API is accessible."""
        start_time = time.monotonic()

        try:
            response = await self._client.get(
                "https://api.groq.com/openai/v1/models",
            )
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                data = response.json()
                models = [m["id"] for m in data.get("data", [])]
                return ProviderHealth(
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                    last_check=datetime.utcnow(),
                    models_available=models,
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
                error="Cannot connect to Groq API",
            )
        except Exception as e:
            return ProviderHealth(
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.utcnow(),
                error=str(e),
            )

    def get_capabilities(self, model: str) -> ProviderCapabilities:
        """Get capabilities for a Groq model."""
        return self._capabilities.get(model, ProviderCapabilities())

    async def list_models(self) -> list[str]:
        """List available Groq models."""
        try:
            response = await self._client.get(
                "https://api.groq.com/openai/v1/models",
            )
            if response.status_code == 200:
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            pass
        return list(self._capabilities.keys())

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
