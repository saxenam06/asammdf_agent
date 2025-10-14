"""
MCP Client for connecting to Windows-MCP server using MCP SDK
Pure async with pattern - no complex event loop management
"""

import os
import json
import asyncio
from typing import Any, Dict, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import nest_asyncio

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema, ExecutionResult

# Allow nested event loops
nest_asyncio.apply()


class MCPClient:
    """
    Simplified MCP client using pure async with pattern

    Usage:
        async with MCPClient() as client:
            result = await client.call_tool('Tool-Name', {'arg': 'value'})
    """

    def __init__(self, config_path: str = None, server_name: str = 'windows-mcp'):
        """Initialize MCP client"""
        if config_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'mcp_config.json')

        self.config_path = config_path
        self.server_name = server_name
        self.session = None
        self._load_config()

    def _load_config(self):
        """Load MCP server configuration"""
        with open(self.config_path, 'r') as f:
            config = json.load(f)
            self.server_configs = config.get('mcpServers', {})

    async def __aenter__(self):
        """
        Connect using pure async with pattern:

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
        """
        config = self.server_configs.get(self.server_name)
        if not config:
            raise ValueError(f"Server '{self.server_name}' not found in config")

        server_params = StdioServerParameters(
            command=config['command'],
            args=config.get('args', []),
            env=config.get('env')
        )

        # Enter stdio_client context
        self._stdio_ctx = stdio_client(server_params)
        self.read, self.write = await self._stdio_ctx.__aenter__()

        # Enter ClientSession context
        self._session_ctx = ClientSession(self.read, self.write)
        self.session = await self._session_ctx.__aenter__()

        # Initialize the connection
        await self.session.initialize()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect - close contexts in reverse order"""
        # Close session first
        if hasattr(self, '_session_ctx'):
            await self._session_ctx.__aexit__(exc_type, exc_val, exc_tb)

        # Then close stdio
        if hasattr(self, '_stdio_ctx'):
            await self._stdio_ctx.__aexit__(exc_type, exc_val, exc_tb)

        return False

    # Async methods for tool interaction
    async def list_tools(self) -> List[Dict]:
        """List available tools from MCP server"""
        if self.session is None:
            raise RuntimeError("Not connected. Use 'async with MCPClient()' context manager.")

        tools_response = await self.session.list_tools()
        tool_info = []
        if hasattr(tools_response, 'tools'):
            for tool in tools_response.tools:
                tool_info.append({
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.inputSchema
                })
        return tool_info

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a tool on the MCP server"""
        if self.session is None:
            raise RuntimeError("Not connected. Use 'async with MCPClient()' context manager.")
        return await self.session.call_tool(tool_name, arguments or {})

    async def execute_action(self, action: ActionSchema) -> ExecutionResult:
        """Execute a single action"""
        reasoning = f" - {action.reasoning}" if action.reasoning else ""
        print(f"[Executing] {action.tool_name} with args {action.tool_arguments}{reasoning}")

        try:
            result = await self.call_tool(action.tool_name, action.tool_arguments)

            # Extract text from result
            if hasattr(result, 'content') and result.content:
                output_text = result.content[0].text
            else:
                output_text = str(result)

            print(f"  -> {output_text[:200]}...")

            return ExecutionResult(
                success=True,
                action=action.tool_name,
                evidence=output_text
            )

        except Exception as e:
            print(f"  X Execution failed: {e}")
            return ExecutionResult(
                success=False,
                action=action.tool_name,
                error=str(e)
            )

    async def get_tools_description(self, tools: List = None) -> str:
        """Format tools for LLM"""
        if tools is None:
            tools = await self.list_tools()

        descriptions = []
        for tool in tools:
            name = tool.get('name', 'Unknown')
            desc = tool.get('description', 'No description')
            schema = tool.get('schema', {})

            properties = schema.get('properties', {})
            required = schema.get('required', [])

            params = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'any')
                param_desc = param_info.get('description', '')
                is_required = ' (required)' if param_name in required else ' (optional)'

                if param_type == 'array':
                    items_type = param_info.get('items', {}).get('type', 'any')
                    param_type = f'array of {items_type}'

                if 'enum' in param_info:
                    enum_values = ', '.join(f'"{v}"' for v in param_info['enum'])
                    param_type = f'{param_type} ({enum_values})'

                params.append(f"    - {param_name}: {param_type}{is_required} - {param_desc}")

            params_str = '\n'.join(params) if params else '    (no parameters)'
            descriptions.append(f"- {name}: {desc}\n  Arguments:\n{params_str}")

        return '\n\n'.join(descriptions)

    async def get_valid_tool_names(self, tools: List = None) -> List[str]:
        """Extract list of valid tool names"""
        if tools is None:
            tools = await self.list_tools()
        return [tool.get('name') for tool in tools if tool.get('name')]

    # ============================================================================
    # Sync wrappers for backward compatibility with existing workflow
    # Uses nest_asyncio to allow running async code from sync contexts
    # ============================================================================

    def list_tools_sync(self) -> List[Dict]:
        """Sync wrapper for list_tools"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.list_tools())

    def get_tools_description_sync(self, tools: List = None) -> str:
        """Sync wrapper for get_tools_description"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_tools_description(tools))

    def get_valid_tool_names_sync(self, tools: List = None) -> List[str]:
        """Sync wrapper for get_valid_tool_names"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_valid_tool_names(tools))

    def call_tool_sync(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Sync wrapper for call_tool"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.call_tool(tool_name, arguments))

    def execute_action_sync(self, action: ActionSchema) -> ExecutionResult:
        """Sync wrapper for execute_action"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.execute_action(action))


if __name__ == "__main__":
    """Test MCP client with pure async with pattern"""
    import asyncio

    async def test():
        print("\n" + "="*80)
        print("Testing Pure Async MCPClient")
        print("="*80 + "\n")

        async with MCPClient() as client:
            # List tools
            tools = await client.list_tools()
            print(f"Found {len(tools)} tools")

            # Call a tool
            result = await client.call_tool("Wait-Tool", {"duration": 1})
            print("Wait-Tool executed successfully")

            # Execute action
            test_action = ActionSchema(
                tool_name="Wait-Tool",
                tool_arguments={"duration": 1},
                reasoning="Wait 1 second"
            )
            exec_result = await client.execute_action(test_action)
            print(f"Action success: {exec_result.success}")

        print("\n" + "="*80)
        print("Tests completed!")
        print("="*80)

    asyncio.run(test())
