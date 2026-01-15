"""
Base Skill Interface - Skills are deterministic programs.

Skills are NOT prompts. They are structured programs that:
1. Receive a validated intent
2. Call tools in a defined sequence
3. Make model calls only for specific sub-tasks
4. Return structured results with undo information
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from atlas.core.models import (
    Change,
    Intent,
    IntentType,
    Receipt,
    RiskLevel,
    ToolCall,
    UndoStep,
)
from atlas.providers import ProviderRegistry


@dataclass
class SkillContext:
    """Context provided to skills during execution."""
    
    intent: Intent
    receipt: Receipt
    providers: ProviderRegistry
    user_id: str | None = None
    
    # Tools registry will be injected
    tools: Any = None


@dataclass
class SkillResult:
    """Result of skill execution."""
    
    success: bool
    tool_calls: list[ToolCall] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    undo_steps: list[UndoStep] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Skill(ABC):
    """
    Base class for all ATLAS skills.
    
    Skills are deterministic programs that execute intents.
    Each skill handles one or more intent types.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier."""
        ...

    @property
    @abstractmethod
    def intent_types(self) -> list[IntentType]:
        """Intent types this skill handles."""
        ...

    @property
    @abstractmethod
    def risk_level(self) -> RiskLevel:
        """Risk level for this skill's operations."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of the skill."""
        return ""

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """
        Execute the skill with the given context.
        
        Args:
            context: Execution context with intent, tools, etc.
            
        Returns:
            SkillResult with tool calls, changes, and undo steps
        """
        ...

    def can_handle(self, intent: Intent) -> bool:
        """Check if this skill can handle the given intent."""
        return intent.type in self.intent_types
