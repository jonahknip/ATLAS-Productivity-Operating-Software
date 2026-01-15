"""
ATLAS Executor - Main execution pipeline.

The executor is responsible for:
1. Receiving user input
2. Routing to the appropriate model
3. Normalizing and validating output
4. Managing fallbacks
5. Executing skills and tools
6. ALWAYS producing a receipt (success or failure)

This is the core of the reliability engine.
"""

import time
from datetime import datetime
from typing import Any, TYPE_CHECKING

from atlas.config import get_settings
from atlas.core.fallback import FallbackManager
from atlas.core.fallback.manager import FallbackAction
from atlas.core.models import (
    FallbackTrigger,
    Intent,
    IntentType,
    JobClass,
    ModelAttempt,
    Receipt,
    ReceiptStatus,
    RiskLevel,
    RoutingProfile,
)
from atlas.core.normalizer import JSONNormalizer
from atlas.core.validator import Validator
from atlas.providers import ProviderRegistry
from atlas.providers.base import CompletionRequest, ProviderError

if TYPE_CHECKING:
    from atlas.skills.registry import SkillRegistry
    from atlas.tools.registry import ToolRegistry


class Executor:
    """
    Main execution engine for ATLAS.
    
    Orchestrates the full pipeline from user input to receipt.
    Guarantees a receipt is produced for every execution attempt.
    """

    # Intent classification prompt template
    INTENT_PROMPT = """Classify the following user input into one of these intent types:
- CAPTURE_TASKS: User wants to create or capture tasks/todos
- PLAN_DAY: User wants to plan their day or schedule
- PROCESS_MEETING_NOTES: User has meeting notes to process
- SEARCH_SUMMARIZE: User wants to search or summarize information
- BUILD_WORKFLOW: User wants to create automation
- UNKNOWN: Cannot classify or general query

User input: "{input}"

Respond ONLY with valid JSON (no markdown, no explanation):
{{"type": "<INTENT_TYPE>", "confidence": <0.0-1.0>, "parameters": {{}}, "raw_entities": ["entity1", "entity2"]}}"""

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        fallback_manager: FallbackManager | None = None,
        skill_registry: "SkillRegistry | None" = None,
        tool_registry: "ToolRegistry | None" = None,
    ):
        self.providers = provider_registry
        self.fallback = fallback_manager or FallbackManager()
        self.normalizer = JSONNormalizer()
        self.validator = Validator()
        self.settings = get_settings()
        self.skills = skill_registry
        self.tools = tool_registry

    async def execute(
        self,
        user_input: str,
        routing_profile: RoutingProfile = RoutingProfile.BALANCED,
        profile_id: str | None = None,
    ) -> Receipt:
        """
        Execute a user request and return a receipt.
        
        This method ALWAYS returns a receipt, even on failure.
        The receipt contains the full audit trail of what happened.
        
        Args:
            user_input: The user's natural language input
            routing_profile: Which routing profile to use
            profile_id: Optional user profile ID
            
        Returns:
            Receipt with execution results (success or failure)
        """
        # Initialize receipt - this will be returned no matter what
        receipt = Receipt(
            user_input=user_input,
            profile_id=profile_id,
            status=ReceiptStatus.PENDING_CONFIRM,
        )

        try:
            # Step 1: Classify intent
            intent = await self._classify_intent(
                user_input, routing_profile, receipt
            )

            if intent:
                receipt.intent_final = intent
                
                # Step 2: Execute skill if available
                if self.skills and self.tools:
                    skill_result = await self._execute_skill(intent, receipt)
                    
                    if skill_result:
                        # Copy results from skill execution to receipt
                        receipt.tool_calls.extend(skill_result.tool_calls)
                        receipt.changes.extend(skill_result.changes)
                        receipt.undo.extend(skill_result.undo_steps)
                        receipt.warnings.extend(skill_result.warnings)
                        
                        if skill_result.errors:
                            receipt.errors.extend(skill_result.errors)
                        
                        # Set status based on skill success
                        if skill_result.success:
                            receipt.status = ReceiptStatus.SUCCESS
                        else:
                            receipt.status = ReceiptStatus.PARTIAL if receipt.tool_calls else ReceiptStatus.FAILED
                    else:
                        # No skill found for this intent
                        receipt.status = ReceiptStatus.SUCCESS
                        receipt.warnings.append(f"No skill registered for intent: {intent.type.value}")
                else:
                    # No skill/tool registries - just classification
                    receipt.status = ReceiptStatus.SUCCESS
                    receipt.warnings.append("Skill execution not available")
            else:
                # Classification failed after all retries
                receipt.status = ReceiptStatus.FAILED
                receipt.errors.append("Failed to classify intent after all attempts")

        except Exception as e:
            # Catch-all to ensure we always return a receipt
            receipt.status = ReceiptStatus.FAILED
            receipt.errors.append(f"Unexpected error: {str(e)}")

        return receipt

    async def _classify_intent(
        self,
        user_input: str,
        routing_profile: RoutingProfile,
        receipt: Receipt,
    ) -> Intent | None:
        """
        Classify user input into an intent using the reliability pipeline.
        
        Implements the full retry/fallback logic per spec:
        - 2 attempts per model
        - Max 3 models total
        
        Updates receipt.models_attempted as it goes.
        """
        job_class = JobClass.INTENT_ROUTING
        attempts: list[ModelAttempt] = []

        # Get initial model
        provider_name, model_name = self.fallback.get_first_model(
            routing_profile, job_class
        )

        while True:
            # Check if provider is available
            provider = self.providers.get(provider_name)
            if not provider:
                # Provider not registered, try fallback
                attempt = ModelAttempt(
                    provider=provider_name,
                    model=model_name,
                    attempt_number=len([a for a in attempts if a.provider == provider_name and a.model == model_name]) + 1,
                    success=False,
                    fallback_trigger=FallbackTrigger.PROVIDER_DOWN,
                )
                attempts.append(attempt)
                receipt.models_attempted.append(attempt)
                receipt.warnings.append(f"Provider '{provider_name}' not available")
                
                decision = self.fallback.decide(
                    FallbackTrigger.PROVIDER_DOWN,
                    attempts,
                    routing_profile,
                    job_class,
                )
                
                if decision.action == FallbackAction.FAIL:
                    return None
                
                provider_name = decision.next_provider or provider_name
                model_name = decision.next_model or model_name
                continue

            # Determine if this is a repair attempt
            current_attempt_num = len([
                a for a in attempts 
                if a.provider == provider_name and a.model == model_name
            ]) + 1
            use_repair = current_attempt_num > 1

            # Build prompt
            prompt = self._build_intent_prompt(user_input, use_repair)

            # Make the model call
            start_time = time.monotonic()
            try:
                response = await provider.complete(
                    CompletionRequest(
                        messages=[{"role": "user", "content": prompt}],
                        model=model_name,
                        temperature=0.3,  # Lower temp for classification
                        json_mode=True,
                    )
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)

                # Try to normalize the output
                norm_result = self.normalizer.normalize(response.content)

                if not norm_result.success:
                    # JSON normalization failed
                    attempt = ModelAttempt(
                        provider=provider_name,
                        model=model_name,
                        attempt_number=current_attempt_num,
                        success=False,
                        fallback_trigger=FallbackTrigger.INVALID_JSON,
                        latency_ms=latency_ms,
                    )
                    attempts.append(attempt)
                    receipt.models_attempted.append(attempt)
                    
                    if norm_result.repairs_applied:
                        receipt.warnings.append(
                            f"JSON repairs attempted: {norm_result.repairs_applied}"
                        )

                    decision = self.fallback.decide(
                        FallbackTrigger.INVALID_JSON,
                        attempts,
                        routing_profile,
                        job_class,
                    )

                    if decision.action == FallbackAction.FAIL:
                        return None

                    provider_name = decision.next_provider or provider_name
                    model_name = decision.next_model or model_name
                    continue

                # Try to validate the intent
                val_result = self.validator.validate_intent(norm_result.data or {})

                if not val_result.valid:
                    # Validation failed
                    attempt = ModelAttempt(
                        provider=provider_name,
                        model=model_name,
                        attempt_number=current_attempt_num,
                        success=False,
                        fallback_trigger=FallbackTrigger.VALIDATION_ERROR,
                        latency_ms=latency_ms,
                    )
                    attempts.append(attempt)
                    receipt.models_attempted.append(attempt)
                    
                    error_msgs = [f"{e.field}: {e.message}" for e in val_result.errors]
                    receipt.warnings.append(f"Validation errors: {error_msgs}")

                    decision = self.fallback.decide(
                        FallbackTrigger.VALIDATION_ERROR,
                        attempts,
                        routing_profile,
                        job_class,
                    )

                    if decision.action == FallbackAction.FAIL:
                        return None

                    provider_name = decision.next_provider or provider_name
                    model_name = decision.next_model or model_name
                    continue

                # Success!
                attempt = ModelAttempt(
                    provider=provider_name,
                    model=model_name,
                    attempt_number=current_attempt_num,
                    success=True,
                    latency_ms=latency_ms,
                )
                attempts.append(attempt)
                receipt.models_attempted.append(attempt)

                return val_result.intent

            except ProviderError as e:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                
                # Determine trigger based on error type
                if "rate limit" in str(e).lower():
                    trigger = FallbackTrigger.RATE_LIMIT
                else:
                    trigger = FallbackTrigger.PROVIDER_DOWN

                attempt = ModelAttempt(
                    provider=provider_name,
                    model=model_name,
                    attempt_number=current_attempt_num,
                    success=False,
                    fallback_trigger=trigger,
                    latency_ms=latency_ms,
                )
                attempts.append(attempt)
                receipt.models_attempted.append(attempt)
                receipt.warnings.append(f"Provider error: {str(e)}")

                decision = self.fallback.decide(
                    trigger,
                    attempts,
                    routing_profile,
                    job_class,
                )

                if decision.action == FallbackAction.FAIL:
                    return None

                provider_name = decision.next_provider or provider_name
                model_name = decision.next_model or model_name
                continue

            except Exception as e:
                # Unexpected error
                latency_ms = int((time.monotonic() - start_time) * 1000)
                
                attempt = ModelAttempt(
                    provider=provider_name,
                    model=model_name,
                    attempt_number=current_attempt_num,
                    success=False,
                    fallback_trigger=FallbackTrigger.PROVIDER_DOWN,
                    latency_ms=latency_ms,
                )
                attempts.append(attempt)
                receipt.models_attempted.append(attempt)
                receipt.errors.append(f"Unexpected error during classification: {str(e)}")

                decision = self.fallback.decide(
                    FallbackTrigger.PROVIDER_DOWN,
                    attempts,
                    routing_profile,
                    job_class,
                )

                if decision.action == FallbackAction.FAIL:
                    return None

                provider_name = decision.next_provider or provider_name
                model_name = decision.next_model or model_name

    def _build_intent_prompt(self, user_input: str, is_repair: bool) -> str:
        """Build the intent classification prompt."""
        base_prompt = self.INTENT_PROMPT.format(input=user_input)
        
        if is_repair:
            return base_prompt + """

IMPORTANT: Your previous response was not valid JSON. 
Please respond with ONLY a valid JSON object, no markdown formatting, no explanation text.
Example: {"type": "CAPTURE_TASKS", "confidence": 0.9, "parameters": {}, "raw_entities": ["task1"]}"""
        
        return base_prompt

    async def _execute_skill(
        self,
        intent: Intent,
        receipt: Receipt,
    ):
        """
        Execute the appropriate skill for the given intent.
        
        Args:
            intent: The classified intent
            receipt: The receipt to update
            
        Returns:
            SkillResult or None if no skill found
        """
        if not self.skills or not self.tools:
            return None
        
        # Check if we have a skill for this intent
        skill = self.skills.get_for_intent(intent)
        if not skill:
            return None
        
        # Import here to avoid circular dependency
        from atlas.skills.base import SkillContext
        
        # Build skill context
        context = SkillContext(
            intent=intent,
            receipt=receipt,
            providers=self.providers,
            user_id=receipt.profile_id,
            tools=self.tools,
        )
        
        # Execute the skill
        return await skill.execute(context)
