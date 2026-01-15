"""
Fallback Manager - Deterministic retry and fallback logic.

Implements the spec-locked retry/fallback policy:
- 2 attempts per model (normal → json repair prompt)
- max 3 models total per request
- deterministic fallback triggers

This ensures ATLAS has bounded retry behavior and
predictable failure modes.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from atlas.core.models import FallbackTrigger, JobClass, ModelAttempt, RoutingProfile


class FallbackAction(str, Enum):
    """What the fallback manager recommends."""

    RETRY_SAME_MODEL = "RETRY_SAME_MODEL"  # Try again with repair prompt
    FALLBACK_NEXT_MODEL = "FALLBACK_NEXT_MODEL"  # Move to next model in chain
    FAIL = "FAIL"  # No more options


@dataclass
class FallbackDecision:
    """Decision from fallback manager."""

    action: FallbackAction
    reason: str
    next_provider: str | None = None
    next_model: str | None = None
    use_repair_prompt: bool = False


@dataclass
class ModelChain:
    """Ordered list of models to try for a job."""

    models: list[tuple[str, str]]  # [(provider, model), ...]


class FallbackManager:
    """
    Deterministic retry and fallback logic.

    Enforces caps from spec:
    - max_attempts_per_model: 2
    - max_models_per_request: 3
    """

    def __init__(
        self,
        max_attempts_per_model: int = 2,
        max_models_per_request: int = 3,
    ):
        self.max_attempts_per_model = max_attempts_per_model
        self.max_models_per_request = max_models_per_request

        # Model chains by profile and job class
        # Cloud-first for production, with Ollama fallback for local dev
        self._chains: dict[tuple[RoutingProfile, JobClass], ModelChain] = {
            # Offline - local only (won't work in cloud)
            (RoutingProfile.OFFLINE, JobClass.INTENT_ROUTING): ModelChain(
                [("ollama", "llama3.2:1b"), ("ollama", "llama3.2"), ("ollama", "mistral")]
            ),
            (RoutingProfile.OFFLINE, JobClass.PLANNING): ModelChain(
                [("ollama", "llama3.2:1b"), ("ollama", "llama3.2"), ("ollama", "mistral")]
            ),
            (RoutingProfile.OFFLINE, JobClass.EXTRACTION): ModelChain(
                [("ollama", "llama3.2:1b"), ("ollama", "llama3.2"), ("ollama", "mistral")]
            ),
            # Balanced - cloud first, local fallback (works in cloud and local)
            (RoutingProfile.BALANCED, JobClass.INTENT_ROUTING): ModelChain(
                [("openai", "gpt-4o-mini"), ("openai", "gpt-4o"), ("ollama", "llama3.2:1b")]
            ),
            (RoutingProfile.BALANCED, JobClass.PLANNING): ModelChain(
                [("openai", "gpt-4o-mini"), ("openai", "gpt-4o"), ("ollama", "llama3.2:1b")]
            ),
            (RoutingProfile.BALANCED, JobClass.EXTRACTION): ModelChain(
                [("openai", "gpt-4o-mini"), ("ollama", "llama3.2:1b")]
            ),
            # Accuracy - cloud first, best models
            (RoutingProfile.ACCURACY, JobClass.INTENT_ROUTING): ModelChain(
                [("openai", "gpt-4o"), ("openai", "gpt-4o-mini"), ("ollama", "llama3.2:1b")]
            ),
            (RoutingProfile.ACCURACY, JobClass.PLANNING): ModelChain(
                [("openai", "gpt-4o"), ("openai", "gpt-4o-mini")]
            ),
            (RoutingProfile.ACCURACY, JobClass.EXTRACTION): ModelChain(
                [("openai", "gpt-4o"), ("openai", "gpt-4o-mini")]
            ),
        }

        # Set defaults for missing combinations
        self._set_defaults()

    def _set_defaults(self) -> None:
        """Fill in default chains for any missing profile/job combinations."""
        for profile in RoutingProfile:
            for job_class in JobClass:
                key = (profile, job_class)
                if key not in self._chains:
                    # Use the intent routing chain as default
                    default_key = (profile, JobClass.INTENT_ROUTING)
                    if default_key in self._chains:
                        self._chains[key] = self._chains[default_key]
                    else:
                        # Ultimate fallback
                        self._chains[key] = ModelChain([("ollama", "llama3.2:1b")])

    def get_model_chain(
        self, profile: RoutingProfile, job_class: JobClass
    ) -> list[tuple[str, str]]:
        """Get the model chain for a profile and job class."""
        chain = self._chains.get((profile, job_class))
        if chain:
            return chain.models[: self.max_models_per_request]
        return [("ollama", "llama3.2:1b")]

    def get_first_model(
        self, profile: RoutingProfile, job_class: JobClass
    ) -> tuple[str, str]:
        """Get the first model to try."""
        chain = self.get_model_chain(profile, job_class)
        return chain[0] if chain else ("ollama", "llama3.2:1b")

    def decide(
        self,
        trigger: FallbackTrigger,
        attempts: list[ModelAttempt],
        profile: RoutingProfile,
        job_class: JobClass,
    ) -> FallbackDecision:
        """
        Decide what to do after a failure.

        Args:
            trigger: What caused the failure
            attempts: History of attempts so far
            profile: Current routing profile
            job_class: Current job class

        Returns:
            FallbackDecision with recommended action
        """
        if not attempts:
            return FallbackDecision(
                action=FallbackAction.FAIL,
                reason="No attempts recorded - invalid state",
            )

        current_attempt = attempts[-1]
        current_model = (current_attempt.provider, current_attempt.model)

        # Count attempts for current model
        current_model_attempts = sum(
            1 for a in attempts if (a.provider, a.model) == current_model
        )

        # Check if we can retry same model
        if (
            current_model_attempts < self.max_attempts_per_model
            and trigger in {FallbackTrigger.INVALID_JSON, FallbackTrigger.VALIDATION_ERROR}
        ):
            return FallbackDecision(
                action=FallbackAction.RETRY_SAME_MODEL,
                reason=f"Retry with repair prompt (attempt {current_model_attempts + 1}/{self.max_attempts_per_model})",
                next_provider=current_attempt.provider,
                next_model=current_attempt.model,
                use_repair_prompt=True,
            )

        # Check if we can fall back to next model
        chain = self.get_model_chain(profile, job_class)
        unique_models_tried = set((a.provider, a.model) for a in attempts)

        if len(unique_models_tried) >= self.max_models_per_request:
            return FallbackDecision(
                action=FallbackAction.FAIL,
                reason=f"Exhausted all {self.max_models_per_request} models",
            )

        # Find next model in chain that hasn't been tried
        for provider, model in chain:
            if (provider, model) not in unique_models_tried:
                return FallbackDecision(
                    action=FallbackAction.FALLBACK_NEXT_MODEL,
                    reason=f"Falling back from {current_model} to ({provider}, {model})",
                    next_provider=provider,
                    next_model=model,
                    use_repair_prompt=False,
                )

        return FallbackDecision(
            action=FallbackAction.FAIL,
            reason="No more models in chain to try",
        )

    def should_fallback(self, trigger: FallbackTrigger) -> bool:
        """Check if this trigger type warrants fallback attempts."""
        # All defined triggers warrant fallback
        return trigger in FallbackTrigger

    def configure_chain(
        self,
        profile: RoutingProfile,
        job_class: JobClass,
        models: list[tuple[str, str]],
    ) -> None:
        """
        Configure a custom model chain.

        Args:
            profile: Routing profile
            job_class: Job class
            models: List of (provider, model) tuples
        """
        self._chains[(profile, job_class)] = ModelChain(models)
