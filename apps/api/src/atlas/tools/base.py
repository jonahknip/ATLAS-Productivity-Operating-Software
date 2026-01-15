"""
Base Tool Interface - Tools are deterministic operations.

Tools are pure functions that:
1. Take validated arguments
2. Perform a single operation
3. Return results with undo information
4. Never make model calls
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from atlas.core.models import Change, RiskLevel, UndoStep


@dataclass
class ToolResult:
    """Result of a tool execution."""
    
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    changes: list[Change] = field(default_factory=list)
    undo_step: UndoStep | None = None
    error: str | None = None


class Tool(ABC):
    """
    Base class for all ATLAS tools.
    
    Tools are deterministic, pure functions that perform
    a single operation and provide undo capabilities.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier (e.g., 'TASK_CREATE')."""
        ...

    @property
    @abstractmethod
    def risk_level(self) -> RiskLevel:
        """Risk level for this tool's operations."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of the tool."""
        return ""

    @property
    def requires_confirmation(self) -> bool:
        """Whether this tool requires user confirmation."""
        return self.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool with the given arguments.
        
        Args:
            **kwargs: Tool-specific arguments
            
        Returns:
            ToolResult with data, changes, and optional undo step
        """
        ...

    def get_undo_args(self, result: ToolResult) -> dict[str, Any] | None:
        """
        Get arguments needed to undo this tool's action.
        
        Args:
            result: The result from execute()
            
        Returns:
            Arguments for the undo operation, or None if not undoable
        """
        if result.undo_step:
            return result.undo_step.args
        return None
