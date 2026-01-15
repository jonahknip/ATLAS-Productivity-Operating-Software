"""
MCP Client - HTTP client for communicating with MCP servers.

This module provides a unified interface for calling MCP servers
from the ATLAS API.
"""

import httpx
from typing import Any
from dataclasses import dataclass


@dataclass
class MCPResponse:
    """Response from an MCP server."""
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class MCPClient:
    """
    HTTP client for MCP servers.
    
    Provides methods for calling tools on the various MCP servers
    (Dashboard, Autopilot, Factory).
    """

    def __init__(
        self,
        dashboard_url: str = "http://localhost:3101",
        autopilot_url: str = "http://localhost:3100",
        factory_url: str = "http://localhost:3102",
    ):
        self.dashboard_url = dashboard_url.rstrip("/")
        self.autopilot_url = autopilot_url.rstrip("/")
        self.factory_url = factory_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def call_dashboard(self, tool: str, args: dict[str, Any]) -> MCPResponse:
        """
        Call a tool on the Dashboard MCP server.
        
        Dashboard tools: task.*, note.*, calendar.*, dashboard.*
        """
        return await self._call_tool(self.dashboard_url, tool, args)

    async def call_autopilot(self, tool: str, args: dict[str, Any]) -> MCPResponse:
        """
        Call a tool on the Autopilot MCP server.
        
        Autopilot tools: fs.*, shell.*, git.*, notify.*
        """
        return await self._call_tool(self.autopilot_url, tool, args)

    async def call_factory(self, tool: str, args: dict[str, Any]) -> MCPResponse:
        """
        Call a tool on the Factory MCP server.
        
        Factory tools: project.init, asset.*
        """
        return await self._call_tool(self.factory_url, tool, args)

    async def _call_tool(self, base_url: str, tool: str, args: dict[str, Any]) -> MCPResponse:
        """Call a tool on an MCP server."""
        try:
            response = await self._client.post(
                f"{base_url}/call",
                json={"name": tool, "arguments": args},
            )
            
            if response.status_code == 200:
                data = response.json()
                return MCPResponse(success=True, data=data)
            elif response.status_code == 404:
                return MCPResponse(success=False, error=f"Tool not found: {tool}")
            else:
                return MCPResponse(
                    success=False,
                    error=f"MCP server error: {response.status_code}",
                )
        except httpx.ConnectError:
            return MCPResponse(
                success=False,
                error=f"Cannot connect to MCP server at {base_url}",
            )
        except Exception as e:
            return MCPResponse(success=False, error=str(e))

    async def health_check(self, server: str = "dashboard") -> bool:
        """Check if an MCP server is healthy."""
        url_map = {
            "dashboard": self.dashboard_url,
            "autopilot": self.autopilot_url,
            "factory": self.factory_url,
        }
        base_url = url_map.get(server, self.dashboard_url)
        
        try:
            response = await self._client.get(f"{base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def list_tools(self, server: str = "dashboard") -> list[dict[str, Any]]:
        """List available tools from an MCP server."""
        url_map = {
            "dashboard": self.dashboard_url,
            "autopilot": self.autopilot_url,
            "factory": self.factory_url,
        }
        base_url = url_map.get(server, self.dashboard_url)
        
        try:
            response = await self._client.get(f"{base_url}/tools")
            if response.status_code == 200:
                data = response.json()
                return data.get("tools", [])
        except Exception:
            pass
        return []

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


# Global client instance
_mcp_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Get or create the global MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


async def close_mcp_client():
    """Close the global MCP client."""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.close()
        _mcp_client = None
