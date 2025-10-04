"""
Claude-based executor that uses MCP tools directly
Claude calls Windows-MCP tools via the Anthropic API
"""

import os
import asyncio
from typing import Optional
from anthropic import Anthropic

from agent.execution.mcp_client import get_mcp_client

# Global event loop for consistent async execution
_event_loop = None

def get_event_loop():
    """Get or create the global event loop"""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop


class ClaudeMCPExecutor:
    """
    Executor that lets Claude call Windows-MCP tools directly
    No hardcoded wrapper functions - Claude uses MCP tools natively
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize executor

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        self.loop = get_event_loop()

        # Get MCP client and connect
        self.mcp = get_mcp_client()
        self.loop.run_until_complete(self.mcp.connect('windows-mcp'))

        # Fetch available tools
        self.mcp_tools = self.loop.run_until_complete(self.mcp.list_tools())

        print(f"Loaded {len(self.mcp_tools)} Windows-MCP tools for Claude")

    def execute_task(self, task: str, max_turns: int = 20) -> dict:
        """
        Execute a task by letting Claude call MCP tools

        Args:
            task: Natural language task description
            max_turns: Maximum conversation turns

        Returns:
            Execution results
        """
        messages = [{
            "role": "user",
            "content": task
        }]

        system_prompt = """You are a Windows desktop automation assistant.

You have access to Windows-MCP tools to interact with the desktop:
- State-Tool: Get current desktop state (windows, UI elements, coordinates)
- Click-Tool: Click on UI elements at coordinates
- Type-Tool: Type text into input fields
- Switch-Tool: Switch to an application window
- Drag-Tool: Drag and drop operations
- Key-Tool: Press keyboard keys
- Shortcut-Tool: Press keyboard shortcuts
- Wait-Tool: Wait for specified duration
- And more...

Always use State-Tool first to understand what's on screen before taking actions.
Use coordinates from State-Tool output when calling Click-Tool or Type-Tool.

Be precise and methodical. Verify state after each action."""

        for turn in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=self.mcp_tools
            )

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                # Extract tool uses
                tool_results = []

                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input
                        tool_use_id = content_block.id

                        print(f"\n[Turn {turn+1}] Claude calling: {tool_name}")
                        print(f"  Args: {tool_input}")

                        # Call the MCP tool
                        try:
                            result = self.loop.run_until_complete(
                                self.mcp.call_tool(tool_name, tool_input)
                            )

                            # Extract text content from MCP result
                            if hasattr(result, 'content') and result.content:
                                tool_output = result.content[0].text
                            else:
                                tool_output = str(result)

                            print(f"  Result: {tool_output[:200]}...")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": tool_output
                            })

                        except Exception as e:
                            print(f"  Error: {e}")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": f"Error: {str(e)}",
                                "is_error": True
                            })

                # Add assistant response and tool results to messages
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                messages.append({
                    "role": "user",
                    "content": tool_results
                })

            elif response.stop_reason == "end_turn":
                # Claude is done
                final_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_text += block.text

                print(f"\n[Turn {turn+1}] Claude finished:")
                print(f"  {final_text}")

                return {
                    "success": True,
                    "task": task,
                    "response": final_text,
                    "turns": turn + 1
                }

            else:
                # Unexpected stop reason
                return {
                    "success": False,
                    "task": task,
                    "error": f"Unexpected stop reason: {response.stop_reason}",
                    "turns": turn + 1
                }

        # Max turns reached
        return {
            "success": False,
            "task": task,
            "error": "Max turns reached",
            "turns": max_turns
        }

    def cleanup(self):
        """Cleanup MCP connections"""
        self.loop.run_until_complete(self.mcp.disconnect())


def execute_with_claude_mcp(task: str) -> dict:
    """
    Convenience function to execute a task with Claude + MCP

    Args:
        task: Natural language task description

    Returns:
        Execution results
    """
    executor = ClaudeMCPExecutor()

    try:
        results = executor.execute_task(task)
        return results
    finally:
        executor.cleanup()


if __name__ == "__main__":
    """
    Test Claude MCP executor
    """
    import argparse

    parser = argparse.ArgumentParser(description="Run task with Claude + MCP")
    parser.add_argument(
        "task",
        nargs="?",
        default="Get the state of the desktop and tell me what applications are running",
        help="Task description"
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("Claude + MCP Executor")
    print("="*80)

    results = execute_with_claude_mcp(args.task)

    print("\n" + "="*80)
    if results['success']:
        print("✓ Task completed successfully!")
        print(f"  Response: {results['response']}")
    else:
        print(f"✗ Task failed: {results.get('error')}")
    print(f"  Turns: {results['turns']}")
    print("="*80)
