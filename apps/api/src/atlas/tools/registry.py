"""
Tool Registry - Central management of tools.

The registry provides tool lookup and execution coordination.
"""

from typing import Any

from atlas.core.models import ToolCall, ToolCallStatus
from atlas.tools.base import Tool, ToolResult


class ToolRegistry:
    """
    Central registry for all tools.
    
    Manages tool registration and provides a unified
    interface for tool execution.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        Register a tool.
        
        Args:
            tool: The tool to register
        """
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            True if removed, False if not found
        """
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    def get_tool_info(self) -> list[dict[str, Any]]:
        """Get info about all registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "requires_confirmation": tool.requires_confirmation,
            }
            for tool in self._tools.values()
        ]

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        skip_confirmation: bool = False,
    ) -> tuple[ToolCall, ToolResult | None]:
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments for the tool
            skip_confirmation: Skip confirmation for MEDIUM/HIGH risk tools
            
        Returns:
            Tuple of (ToolCall record, ToolResult or None if pending confirmation)
        """
        tool = self.get(tool_name)
        
        if not tool:
            tool_call = ToolCall(
                tool_name=tool_name,
                args=args,
                status=ToolCallStatus.FAILED,
                error=f"Tool not found: {tool_name}",
            )
            return tool_call, None

        # Check if confirmation is needed
        if tool.requires_confirmation and not skip_confirmation:
            tool_call = ToolCall(
                tool_name=tool_name,
                args=args,
                status=ToolCallStatus.PENDING_CONFIRM,
            )
            return tool_call, None

        # Execute the tool
        try:
            result = await tool.execute(**args)
            
            tool_call = ToolCall(
                tool_name=tool_name,
                args=args,
                status=ToolCallStatus.OK if result.success else ToolCallStatus.FAILED,
                result=result.data,
                error=result.error,
            )
            
            return tool_call, result
            
        except Exception as e:
            tool_call = ToolCall(
                tool_name=tool_name,
                args=args,
                status=ToolCallStatus.FAILED,
                error=str(e),
            )
            return tool_call, None
