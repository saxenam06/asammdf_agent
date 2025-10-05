"""
Simple MCP executor - directly calls MCP tools without abstraction layers
Uses the same pattern as manual_workflow.py
"""

import asyncio
from typing import Optional, List
import sys 
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agent.execution.mcp_client import get_mcp_client
from agent.planning.schemas import ActionSchema, ExecutionResult


class MCPExecutor:
    """
    Executes actions by directly calling MCP tools
    No wrapper methods or string parsing - just direct tool invocation
    """

    def __init__(self, server_name: str = 'windows-mcp'):
        """
        Initialize MCP executor

        Args:
            server_name: Name of MCP server from config
        """
        self.server_name = server_name
        self._mcp_client = None
        self._event_loop = None

    def _get_event_loop(self):
        """Get or create the global event loop"""
        if self._event_loop is None or self._event_loop.is_closed():
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
        return self._event_loop

    def _get_connected_client(self):
        """Get or create connected MCP client"""
        if self._mcp_client is None:
            self._mcp_client = get_mcp_client()
            loop = self._get_event_loop()
            loop.run_until_complete(self._mcp_client.connect(self.server_name))
        return self._mcp_client

    def list_tools(self):
        """
        Get list of available MCP tools with their schemas

        Returns:
            List of tool information dicts with name, description, and schema
        """
        client = self._get_connected_client()
        loop = self._get_event_loop()

        tools = loop.run_until_complete(
            client.list_tools()
        )

        return tools

    def get_tools_description(self, tools: List = None):
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

    def get_valid_tool_names(self, tools: List = None):
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

    def call_tool(self, tool_name: str, tool_arguments: dict = None):
        """
        Call an MCP tool directly and return the raw result
        Simplified interface for manual workflows

        Args:
            tool_name: MCP tool name (e.g., 'Click-Tool', 'State-Tool')
            tool_arguments: Tool arguments dict

        Returns:
            Raw MCP tool result
        """
        if tool_arguments is None:
            tool_arguments = {}

        client = self._get_connected_client()
        loop = self._get_event_loop()

        result = loop.run_until_complete(
            client.call_tool(tool_name, tool_arguments)
        )

        return result

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
            client = self._get_connected_client()
            loop = self._get_event_loop()

            # Call MCP tool directly - same pattern as manual_workflow.py
            result = loop.run_until_complete(
                client.call_tool(action.tool_name, action.tool_arguments)
            )

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

    def cleanup(self):
        """Cleanup MCP connections"""
        if self._mcp_client:
            loop = self._get_event_loop()
            loop.run_until_complete(self._mcp_client.disconnect())
            self._mcp_client = None


if __name__ == "__main__":
    """
    Test MCP executor
    """
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from agent.planning.schemas import ActionSchema

    # Test actions
    test_actions = [
        ActionSchema(
            tool_name="State-Tool",
            tool_arguments={"use_vision": False},
            reasoning="Get desktop state"
        ),
        ActionSchema(
            tool_name="Wait-Tool",
            tool_arguments={"duration": 1},
            reasoning="Wait 1 second"
        )
    ]

    print("\n" + "="*80)
    print("Testing MCP Executor")
    print("="*80 + "\n")

    executor = MCPExecutor()

    try:
        results = executor.execute_actions(test_actions)

        print("\n" + "="*80)
        print("Execution Results:")
        print("="*80)

        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result.action}")
            print(f"   Success: {result.success}")
            if result.error:
                print(f"   Error: {result.error}")
            if result.evidence:
                print(f"   Evidence: {result.evidence[:100]}...")

    finally:
        executor.cleanup()
