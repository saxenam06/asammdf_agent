"""MCP Client using async context manager pattern"""
import os, json, asyncio
from typing import Any, Dict, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import nest_asyncio
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from agent.planning.schemas import ActionSchema, ExecutionResult

nest_asyncio.apply()


class MCPClient:
    """Async MCP client for Windows-MCP server

    Usage:
        async with MCPClient() as client:
            result = await client.call_tool('Tool-Name', {'arg': 'value'})
    """

    def __init__(self, config_path: str = None, server_name: str = 'windows-mcp'):
        if config_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, 'mcp_config.json')

        self.config_path = config_path
        self.server_name = server_name
        self.session = None
        self._load_config()

    def _load_config(self):
        with open(self.config_path, 'r') as f:
            self.server_configs = json.load(f).get('mcpServers', {})

    async def __aenter__(self):
        config = self.server_configs.get(self.server_name)
        if not config:
            raise ValueError(f"Server '{self.server_name}' not found")

        server_params = StdioServerParameters(
            command=config['command'],
            args=config.get('args', []),
            env=config.get('env')
        )

        self._stdio_ctx = stdio_client(server_params)
        self.read, self.write = await self._stdio_ctx.__aenter__()

        self._session_ctx = ClientSession(self.read, self.write)
        self.session = await self._session_ctx.__aenter__()
        await self.session.initialize()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, '_session_ctx'):
            await self._session_ctx.__aexit__(exc_type, exc_val, exc_tb)
        if hasattr(self, '_stdio_ctx'):
            await self._stdio_ctx.__aexit__(exc_type, exc_val, exc_tb)
        return False

    async def list_tools(self) -> List[Dict]:
        if not self.session:
            raise RuntimeError("Not connected")

        tools_response = await self.session.list_tools()
        return [{
            "name": t.name,
            "description": t.description,
            "schema": t.inputSchema
        } for t in tools_response.tools] if hasattr(tools_response, 'tools') else []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        if not self.session:
            raise RuntimeError("Not connected")
        return await self.session.call_tool(tool_name, arguments or {})

    async def execute_action(self, action: ActionSchema) -> ExecutionResult:
        try:
            result = await self.call_tool(action.tool_name, action.tool_arguments)
            output_text = result.content[0].text if hasattr(result, 'content') and result.content else str(result)
            return ExecutionResult(success=True, action=action.tool_name, evidence=output_text)
        except Exception as e:
            return ExecutionResult(success=False, action=action.tool_name, error=str(e))

    async def get_tools_description(self, tools: List = None) -> str:
        if tools is None:
            tools = await self.list_tools()

        descriptions = []
        for tool in tools:
            name, desc = tool.get('name', 'Unknown'), tool.get('description', '')
            schema = tool.get('schema', {})
            properties, required = schema.get('properties', {}), schema.get('required', [])

            params = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'any')
                param_desc = param_info.get('description', '')
                is_req = ' (required)' if param_name in required else ''
                params.append(f"    - {param_name}: {param_type}{is_req} - {param_desc}")

            params_str = '\n'.join(params) if params else '    (no parameters)'
            descriptions.append(f"- {name}: {desc}\n  Arguments:\n{params_str}")

        return '\n\n'.join(descriptions)

    async def get_valid_tool_names(self, tools: List = None) -> List[str]:
        if tools is None:
            tools = await self.list_tools()
        return [tool.get('name') for tool in tools if tool.get('name')]

    def list_tools_sync(self) -> List[Dict]:
        return asyncio.get_event_loop().run_until_complete(self.list_tools())

    def get_tools_description_sync(self, tools: List = None) -> str:
        return asyncio.get_event_loop().run_until_complete(self.get_tools_description(tools))

    def get_valid_tool_names_sync(self, tools: List = None) -> List[str]:
        return asyncio.get_event_loop().run_until_complete(self.get_valid_tool_names(tools))

    def call_tool_sync(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        return asyncio.get_event_loop().run_until_complete(self.call_tool(tool_name, arguments))

    def execute_action_sync(self, action: ActionSchema) -> ExecutionResult:
        return asyncio.get_event_loop().run_until_complete(self.execute_action(action))


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
