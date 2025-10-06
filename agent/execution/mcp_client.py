"""
MCP Client for connecting to Windows-MCP server using MCP SDK
Combines client connection and execution functionality
"""

import os
import json
import asyncio
from typing import Any, Dict, List, Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.planning.schemas import ActionSchema, ExecutionResult

# Disable debugger evaluation timeout warnings for async operations
os.environ.setdefault('PYDEVD_WARN_EVALUATION_TIMEOUT', '30')
os.environ.setdefault('PYDEVD_UNBLOCK_THREADS_TIMEOUT', '10')


class MCPClient:
    """
    Unified MCP client with connection and execution capabilities
    Supports both async and sync interfaces for different workflow types
    """

    def __init__(self, config_path: str = None, server_name: str = 'windows-mcp'):
        """
        Initialize MCP client

        Args:
            config_path: Path to mcp_config.json (defaults to project root)
            server_name: Name of MCP server from config
        """
        if config_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'mcp_config.json')

        self.config_path = config_path
        self.server_name = server_name
        self.session = None
        self.read = None
        self.write = None
        self._exit_stack = None
        self._event_loop = None
        self._load_config()

    def _load_config(self):
        """Load MCP server configuration"""
        with open(self.config_path, 'r') as f:
            config = json.load(f)
            self.server_configs = config.get('mcpServers', {})

    def _get_event_loop(self):
        """Get or create the global event loop"""
        if self._event_loop is None or self._event_loop.is_closed():
            try:
                self._event_loop = asyncio.get_event_loop()
                if self._event_loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                self._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._event_loop)
        return self._event_loop

    def _run_async(self, coro):
        """Run async coroutine, handling nested event loop issues"""
        try:
            # Check if we're already in an event loop
            asyncio.get_running_loop()
            # We're in an async context - use nest_asyncio or create task
            import nest_asyncio
            nest_asyncio.apply()
            loop = self._get_event_loop()
            return loop.run_until_complete(coro)
        except RuntimeError:
            # Not in async context, run normally
            loop = self._get_event_loop()
            return loop.run_until_complete(coro)
        except ImportError:
            # nest_asyncio not available, fall back to normal run
            loop = self._get_event_loop()
            return loop.run_until_complete(coro)

    async def connect(self, server_name: str = None):
        """
        Connect to MCP server using stdio transport

        Args:
            server_name: Name of server from config (uses default if None)
        """
        if self.session is not None:
            return  # Already connected

        if server_name is None:
            server_name = self.server_name

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

    def ensure_connected(self):
        """Ensure client is connected (sync wrapper)"""
        if self.session is None:
            self._run_async(self.connect())

    async def _list_tools_async(self) -> List[Dict]:
        """Internal async method to list tools from MCP server"""
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

    def list_tools(self) -> List[Dict]:
        """
        Get list of available tools from MCP server

        Returns:
            List of tool information dictionaries
        """
        self.ensure_connected()
        return self._run_async(self._list_tools_async())

    def get_tools_description(self, tools: List = None) -> str:
        """
        Format MCP tools into a readable description for the LLM

        Args:
            tools: List of tool dictionaries from MCP (fetches if None)

        Returns:
            Formatted string describing all tools and their parameters
        """
        if tools is None:
            tools = self.list_tools()

        descriptions = []
        for tool in tools:
            name = tool.get('name', 'Unknown')
            desc = tool.get('description', 'No description')
            schema = tool.get('schema', {})

            # Extract parameters from schema
            properties = schema.get('properties', {})
            required = schema.get('required', [])

            # Format parameters
            params = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'any')
                param_desc = param_info.get('description', '')
                is_required = ' (required)' if param_name in required else ' (optional)'

                # Handle array types
                if param_type == 'array':
                    items_type = param_info.get('items', {}).get('type', 'any')
                    param_type = f'array of {items_type}'

                # Handle enum values
                if 'enum' in param_info:
                    enum_values = ', '.join(f'"{v}"' for v in param_info['enum'])
                    param_type = f'{param_type} ({enum_values})'

                params.append(f"    - {param_name}: {param_type}{is_required} - {param_desc}")

            params_str = '\n'.join(params) if params else '    (no parameters)'

            descriptions.append(f"- {name}: {desc}\n  Arguments:\n{params_str}")

        return '\n\n'.join(descriptions)

    def get_valid_tool_names(self, tools: List = None) -> List[str]:
        """
        Extract list of valid tool names from MCP tools

        Args:
            tools: List of tool dictionaries from MCP (fetches if None)

        Returns:
            List of tool names
        """
        if tools is None:
            tools = self.list_tools()

        return [tool.get('name') for tool in tools if tool.get('name')]

    async def _call_tool_async(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Internal async method to call a tool on the MCP server"""
        if self.session is None:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        result = await self.session.call_tool(tool_name, arguments or {})
        return result

    def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Call a tool on the MCP server

        Args:
            tool_name: MCP tool name (e.g., 'Click-Tool', 'Type-Tool', 'State-Tool')
            arguments: Tool arguments dict

        Returns:
            Tool response (raw result from MCP server)
        """
        self.ensure_connected()
        return self._run_async(self._call_tool_async(tool_name, arguments))

    def execute_action(self, action: ActionSchema) -> ExecutionResult:
        """
        Execute a single action by calling the MCP tool directly

        Args:
            action: Action to execute (contains tool_name and tool_arguments)

        Returns:
            Execution result
        """
        reasoning = f" - {action.reasoning}" if action.reasoning else ""
        print(f"[Executing] {action.tool_name} with args {action.tool_arguments}{reasoning}")

        try:
            # Call MCP tool directly
            result = self.call_tool(action.tool_name, action.tool_arguments)

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

    def execute_actions(self, actions: List[ActionSchema]) -> List[ExecutionResult]:
        """
        Execute a sequence of actions

        Args:
            actions: List of actions to execute

        Returns:
            List of execution results
        """
        results = []
        for i, action in enumerate(actions, 1):
            print(f"\n[Step {i}/{len(actions)}]")
            result = self.execute_action(action)
            results.append(result)

            # Stop on first failure
            if not result.success:
                print(f"\nX Stopping execution due to failure at step {i}")
                break

        return results

    async def disconnect(self):
        """Disconnect from MCP server"""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self.session = None
            self.read = None
            self.write = None
            self._exit_stack = None

    def cleanup(self):
        """Cleanup MCP connections (sync wrapper)"""
        if self._exit_stack:
            try:
                self._run_async(self.disconnect())
            except (RuntimeError, Exception) as e:
                # Ignore cleanup errors - they're typically due to event loop issues
                # but resources will be cleaned up when process exits
                pass
            finally:
                self.session = None
                self._exit_stack = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Global MCP client instance (lazy initialization)
_mcp_client = None

def get_mcp_client() -> MCPClient:
    """
    Get the global MCP client instance (creates if needed)
    This is the recommended way to access the client from workflows
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


if __name__ == "__main__":
    """
    Test MCP client with both sync and async execution
    """
    print("\n" + "="*80)
    print("Testing MCP Client")
    print("="*80 + "\n")

    # Test 1: Sync execution
    print("[Test 1] Sync tool execution")
    print("-" * 40)

    client = get_mcp_client()

    # List tools
    tools = client.list_tools()
    print(f"Found {len(tools)} tools")

    # Call a simple tool
    result = client.call_tool("State-Tool", {"use_vision": False})
    print(f"State-Tool result: {str(result)[:100]}...")

    print("\n[Test 2] Action execution")
    print("-" * 40)

    # Test action execution
    test_action = ActionSchema(
        tool_name="Wait-Tool",
        tool_arguments={"duration": 1},
        reasoning="Wait 1 second"
    )

    exec_result = client.execute_action(test_action)
    print(f"Success: {exec_result.success}")

    # Cleanup
    client.cleanup()

    print("\n" + "="*80)
    print("Tests completed successfully!")
    print("="*80)
