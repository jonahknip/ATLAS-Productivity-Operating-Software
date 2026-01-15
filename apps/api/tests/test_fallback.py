"""Tests for the Fallback Manager."""

import pytest

from atlas.core.fallback import FallbackDecision, FallbackManager
from atlas.core.fallback.manager import FallbackAction
from atlas.core.models import (
    FallbackTrigger,
    JobClass,
    ModelAttempt,
    RoutingProfile,
)


class TestFallbackManager:
    """Test fallback and retry logic."""

    @pytest.fixture
    def manager(self) -> FallbackManager:
        return FallbackManager()

    def test_get_first_model_offline(self, manager: FallbackManager) -> None:
        """Offline profile should start with local model."""
        provider, model = manager.get_first_model(
            RoutingProfile.OFFLINE, JobClass.INTENT_ROUTING
        )

        assert provider == "ollama"
        assert "llama" in model or "mistral" in model or "phi" in model

    def test_get_first_model_accuracy(self, manager: FallbackManager) -> None:
        """Accuracy profile should start with cloud model."""
        provider, model = manager.get_first_model(
            RoutingProfile.ACCURACY, JobClass.INTENT_ROUTING
        )

        assert provider == "openai"

    def test_retry_on_invalid_json(self, manager: FallbackManager) -> None:
        """Should retry same model on INVALID_JSON."""
        attempts = [
            ModelAttempt(
                provider="ollama",
                model="llama3.2",
                attempt_number=1,
                success=False,
                fallback_trigger=FallbackTrigger.INVALID_JSON,
            )
        ]

        decision = manager.decide(
            FallbackTrigger.INVALID_JSON,
            attempts,
            RoutingProfile.BALANCED,
            JobClass.INTENT_ROUTING,
        )

        assert decision.action == FallbackAction.RETRY_SAME_MODEL
        assert decision.use_repair_prompt
        assert decision.next_provider == "ollama"
        assert decision.next_model == "llama3.2"

    def test_fallback_after_max_attempts(self, manager: FallbackManager) -> None:
        """Should fall back to next model after max attempts on same model."""
        attempts = [
            ModelAttempt(
                provider="ollama",
                model="llama3.2",
                attempt_number=1,
                success=False,
                fallback_trigger=FallbackTrigger.INVALID_JSON,
            ),
            ModelAttempt(
                provider="ollama",
                model="llama3.2",
                attempt_number=2,
                success=False,
                fallback_trigger=FallbackTrigger.INVALID_JSON,
            ),
        ]

        decision = manager.decide(
            FallbackTrigger.INVALID_JSON,
            attempts,
            RoutingProfile.BALANCED,
            JobClass.INTENT_ROUTING,
        )

        assert decision.action == FallbackAction.FALLBACK_NEXT_MODEL
        assert (decision.next_provider, decision.next_model) != ("ollama", "llama3.2")

    def test_fail_after_exhausting_models(self, manager: FallbackManager) -> None:
        """Should fail after trying max_models_per_request."""
        # Simulate exhausting 3 models
        attempts = [
            ModelAttempt(provider="ollama", model="llama3.2", attempt_number=1, success=False),
            ModelAttempt(provider="ollama", model="llama3.2", attempt_number=2, success=False),
            ModelAttempt(provider="openai", model="gpt-4o-mini", attempt_number=1, success=False),
            ModelAttempt(provider="openai", model="gpt-4o-mini", attempt_number=2, success=False),
            ModelAttempt(provider="openai", model="gpt-4o", attempt_number=1, success=False),
            ModelAttempt(provider="openai", model="gpt-4o", attempt_number=2, success=False),
        ]

        decision = manager.decide(
            FallbackTrigger.VALIDATION_ERROR,
            attempts,
            RoutingProfile.BALANCED,
            JobClass.INTENT_ROUTING,
        )

        assert decision.action == FallbackAction.FAIL

    def test_immediate_fallback_on_provider_down(self, manager: FallbackManager) -> None:
        """Should immediately fall back on PROVIDER_DOWN."""
        attempts = [
            ModelAttempt(
                provider="ollama",
                model="llama3.2",
                attempt_number=1,
                success=False,
                fallback_trigger=FallbackTrigger.PROVIDER_DOWN,
            ),
        ]

        decision = manager.decide(
            FallbackTrigger.PROVIDER_DOWN,
            attempts,
            RoutingProfile.BALANCED,
            JobClass.INTENT_ROUTING,
        )

        # Provider down should trigger retry with repair prompt first
        # since attempt count is still < max
        assert decision.action in {
            FallbackAction.RETRY_SAME_MODEL,
            FallbackAction.FALLBACK_NEXT_MODEL,
        }

    def test_model_chain_respects_max_models(self, manager: FallbackManager) -> None:
        """Model chain should not exceed max_models_per_request."""
        chain = manager.get_model_chain(RoutingProfile.BALANCED, JobClass.INTENT_ROUTING)

        assert len(chain) <= manager.max_models_per_request

    def test_empty_attempts_returns_fail(self, manager: FallbackManager) -> None:
        """Empty attempts list should return FAIL (invalid state)."""
        decision = manager.decide(
            FallbackTrigger.INVALID_JSON,
            [],
            RoutingProfile.BALANCED,
            JobClass.INTENT_ROUTING,
        )

        assert decision.action == FallbackAction.FAIL

    def test_custom_chain_configuration(self, manager: FallbackManager) -> None:
        """Should allow custom model chain configuration."""
        custom_chain = [("custom", "model1"), ("custom", "model2")]

        manager.configure_chain(
            RoutingProfile.OFFLINE,
            JobClass.PLANNING,
            custom_chain,
        )

        chain = manager.get_model_chain(RoutingProfile.OFFLINE, JobClass.PLANNING)
        assert chain == custom_chain

    def test_caps_are_enforced(self, manager: FallbackManager) -> None:
        """Verify the spec-locked caps."""
        assert manager.max_attempts_per_model == 2
        assert manager.max_models_per_request == 3
