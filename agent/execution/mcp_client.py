"""
MCP Client for connecting to Windows-MCP server using MCP SDK
"""

import os
import json
import asyncio
from typing import Any, Dict, List
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """
    MCP client using official MCP SDK with stdio transport
    """

    def __init__(self, config_path: str = None):
        """
        Initialize MCP client

        Args:
            config_path: Path to mcp_config.json (defaults to project root)
        """
        if config_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'mcp_config.json')

        self.config_path = config_path
        self.session = None
        self.read = None
        self.write = None
        self._exit_stack = None
        self._load_config()

    def _load_config(self):
        """Load MCP server configuration"""
        with open(self.config_path, 'r') as f:
            config = json.load(f)
            self.server_configs = config.get('mcpServers', {})

    async def connect(self, server_name: str):
        """
        Connect to MCP server using stdio transport

        Args:
            server_name: Name of server from config (e.g., 'windows-mcp')
        """
        if self.session is not None:
            return  # Already connected

        config = self.server_configs.get(server_name)
        if not config:
            raise ValueError(f"Server '{server_name}' not found in config")

        command = config['command']
        args = config.get('args', [])

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=config.get('env')
        )

        # Use AsyncExitStack to properly manage nested async context managers
        self._exit_stack = AsyncExitStack()

        # Enter stdio_client context
        self.read, self.write = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )

        # Enter ClientSession context
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(self.read, self.write)
        )

        # Initialize the connection
        await self.session.initialize()

    async def list_tools(self) -> List[Dict]:
        """
        Get list of available tools from MCP server

        Returns:
            List of tool information dictionaries
        """
        if self.session is None:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        tools_response = await self.session.list_tools()

        tool_info = []
        # The response is a ListToolsResult object with a 'tools' attribute
        if hasattr(tools_response, 'tools'):
            for tool in tools_response.tools:
                tool_info.append({
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.inputSchema
                })

        return tool_info

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Call a tool on the MCP server

        Args:
            tool_name: MCP tool name (e.g., 'Click-Tool', 'Type-Tool', 'State-Tool')
            arguments: Tool arguments dict

        Returns:
            Tool response (raw result from MCP server)
        """
        if self.session is None:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        result = await self.session.call_tool(tool_name, arguments or {})
        return result

    async def disconnect(self):
        """Disconnect from MCP server"""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self.session = None
            self.read = None
            self.write = None
            self._exit_stack = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Global MCP client instance (lazy initialization)
_mcp_client = None

def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance (creates if needed)"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client
