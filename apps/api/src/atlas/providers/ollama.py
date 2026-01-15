"""Ollama provider adapter for local model execution."""

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
)


class OllamaAdapter(ProviderAdapter):
    """
    Adapter for Ollama local model server.

    Ollama provides local LLM inference with models like
    Llama, Mistral, Phi, etc.
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

        # Known model capabilities
        self._capabilities: dict[str, ProviderCapabilities] = {
            "llama3.2": ProviderCapabilities(
                strict_json=False,
                tool_calls=False,
                max_tokens=4096,
                context_window=128000,
            ),
            "llama3.2:1b": ProviderCapabilities(
                strict_json=False,
                tool_calls=False,
                max_tokens=4096,
                context_window=128000,
            ),
            "mistral": ProviderCapabilities(
                strict_json=False,
                tool_calls=False,
                max_tokens=4096,
                context_window=32000,
            ),
            "phi3": ProviderCapabilities(
                strict_json=False,
                tool_calls=False,
                max_tokens=4096,
                context_window=128000,
            ),
        }

    @property
    def name(self) -> str:
        return "ollama"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send completion request to Ollama."""
        start_time = time.monotonic()

        # Build Ollama request
        payload = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        if request.json_mode:
            payload["format"] = "json"

        try:
            response = await self._client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = int((time.monotonic() - start_time) * 1000)

            return CompletionResponse(
                content=data.get("message", {}).get("content", ""),
                model=request.model,
                provider=self.name,
                latency_ms=latency_ms,
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                },
            )

        except httpx.ConnectError:
            raise ProviderDownError(self.name, "Cannot connect to Ollama server")
        except httpx.HTTPStatusError as e:
            raise ProviderDownError(self.name, f"Ollama error: {e.response.status_code}")

    async def health_check(self) -> ProviderHealth:
        """Check if Ollama is running and responsive."""
        start_time = time.monotonic()

        try:
            response = await self._client.get(f"{self.base_url}/api/tags")
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                return ProviderHealth(
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency_ms,
                    last_check=datetime.utcnow(),
                    models_available=models,
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
                error="Cannot connect to Ollama server",
            )
        except Exception as e:
            return ProviderHealth(
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.utcnow(),
                error=str(e),
            )

    def get_capabilities(self, model: str) -> ProviderCapabilities:
        """Get capabilities for an Ollama model."""
        # Normalize model name (remove tags like :7b)
        base_model = model.split(":")[0] if ":" in model else model

        return self._capabilities.get(
            model,
            self._capabilities.get(
                base_model,
                ProviderCapabilities(),  # Default capabilities
            ),
        )

    async def list_models(self) -> list[str]:
        """List available Ollama models."""
        try:
            response = await self._client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            pass
        return []

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
