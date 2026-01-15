"""MCP Client module for communicating with MCP servers."""

from atlas.mcp.client import MCPClient, MCPResponse, get_mcp_client, close_mcp_client

__all__ = ["MCPClient", "MCPResponse", "get_mcp_client", "close_mcp_client"]
