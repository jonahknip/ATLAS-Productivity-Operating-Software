"""Provider Registry - Central management of model providers."""

from datetime import datetime
from typing import Any

from atlas.providers.base import (
    HealthStatus,
    ProviderAdapter,
    ProviderCapabilities,
    ProviderHealth,
)


class ProviderRegistry:
    """
    Central registry for model providers.

    Manages registration, health monitoring, and capability queries
    for all configured providers.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderAdapter] = {}
        self._health_cache: dict[str, ProviderHealth] = {}

    def register(self, provider: ProviderAdapter) -> None:
        """
        Register a provider adapter.

        Args:
            provider: The provider adapter to register
        """
        self._providers[provider.name] = provider
        self._health_cache[provider.name] = ProviderHealth(
            status=HealthStatus.UNKNOWN,
            last_check=None,
        )

    def unregister(self, name: str) -> bool:
        """
        Unregister a provider.

        Args:
            name: Provider name to remove

        Returns:
            True if provider was removed, False if not found
        """
        if name in self._providers:
            del self._providers[name]
            self._health_cache.pop(name, None)
            return True
        return False

    def get(self, name: str) -> ProviderAdapter | None:
        """
        Get a provider adapter by name.

        Args:
            name: Provider name (e.g., 'ollama', 'openai')

        Returns:
            ProviderAdapter or None if not found
        """
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """Get list of registered provider names."""
        return list(self._providers.keys())

    async def check_health(self, name: str) -> ProviderHealth:
        """
        Check and cache health for a provider.

        Args:
            name: Provider name

        Returns:
            ProviderHealth status
        """
        provider = self._providers.get(name)
        if not provider:
            return ProviderHealth(
                status=HealthStatus.UNKNOWN,
                error=f"Provider '{name}' not registered",
            )

        health = await provider.health_check()
        self._health_cache[name] = health
        return health

    async def check_all_health(self) -> dict[str, ProviderHealth]:
        """
        Check health of all registered providers.

        Returns:
            Dict of provider name to health status
        """
        results: dict[str, ProviderHealth] = {}
        for name in self._providers:
            results[name] = await self.check_health(name)
        return results

    def get_cached_health(self, name: str) -> ProviderHealth | None:
        """Get cached health status for a provider."""
        return self._health_cache.get(name)

    def get_capabilities(self, provider: str, model: str) -> ProviderCapabilities | None:
        """
        Get capabilities for a provider/model combination.

        Args:
            provider: Provider name
            model: Model identifier

        Returns:
            ProviderCapabilities or None if provider not found
        """
        adapter = self._providers.get(provider)
        if adapter:
            return adapter.get_capabilities(model)
        return None

    def is_available(self, name: str) -> bool:
        """
        Check if a provider is available (healthy or unknown).

        Args:
            name: Provider name

        Returns:
            True if provider might be available
        """
        if name not in self._providers:
            return False

        health = self._health_cache.get(name)
        if not health:
            return True  # Unknown = might be available

        return health.status in {HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNKNOWN}

    async def list_models(self, provider: str) -> list[str]:
        """
        List available models from a provider.

        Args:
            provider: Provider name

        Returns:
            List of model identifiers
        """
        adapter = self._providers.get(provider)
        if adapter:
            return await adapter.list_models()
        return []

    def get_status_summary(self) -> dict[str, Any]:
        """
        Get summary of all providers and their status.

        Returns:
            Dict with provider summaries
        """
        summary: dict[str, Any] = {}
        for name, provider in self._providers.items():
            health = self._health_cache.get(name)
            summary[name] = {
                "registered": True,
                "status": health.status.value if health else "UNKNOWN",
                "last_check": health.last_check.isoformat() if health and health.last_check else None,
                "latency_ms": health.latency_ms if health else None,
                "error": health.error if health else None,
            }
        return summary

    async def close_all(self) -> None:
        """Close all provider connections."""
        for provider in self._providers.values():
            if hasattr(provider, "close"):
                await provider.close()
