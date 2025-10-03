"""Test MCP connection and tool discovery"""

import asyncio
from agent.execution.mcp_client import MCPClient


async def test_mcp_connection():
    # ANSI color codes
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RESET = "\033[0m"
    SEP = "=" * 60

    print(f"{BLUE}Initializing MCP connection...{RESET}")

    # Create client
    client = MCPClient()

    # Connect to server
    await client.connect('windows-mcp')
    print(f"{GREEN}Connected to windows-mcp server{RESET}")

    # List tools
    print(f"{BLUE}Discovering available tools...{RESET}")
    tools = await client.list_tools()

    print(f"{GREEN}Successfully discovered {len(tools)} tools{RESET}")
    print(f"{SEP}")

    # Print tools
    for tool in tools:
        print(f"\nTool: {tool['name']}")
        print(f"   Description: {tool['description']}")
        if tool['schema']:
            print(f"   Schema: {tool['schema']}")

    print(f"\n{SEP}")

    # Disconnect
    await client.disconnect()
    print(f"{GREEN}Disconnected{RESET}")


if __name__ == "__main__":
    asyncio.run(test_mcp_connection())