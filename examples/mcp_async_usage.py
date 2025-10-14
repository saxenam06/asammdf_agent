"""
MCP Client Async Usage Examples
Demonstrates the clean async with pattern for MCP client
"""
import asyncio
from agent.execution.mcp_client import MCPClient


async def example_1_discover_tools():
    """
    Example 1: Discover available MCP tools
    Pattern similar to your discover_tools() function
    """
    print("\n" + "="*60)
    print("Example 1: Discover Tools")
    print("="*60)

    async with MCPClient() as client:
        # Access the session directly for async operations
        print("Discovering available tools...")
        tools_response = await client.session.list_tools()

        # Extract tool information
        tool_info = []
        if hasattr(tools_response, 'tools'):
            for tool in tools_response.tools:
                tool_info.append({
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.inputSchema
                })

        print(f"Successfully discovered {len(tool_info)} tools\n")

        # Show tools
        for i, tool in enumerate(tool_info, 1):
            print(f"{i}. {tool['name']}")
            print(f"   {tool['description'][:80]}...")

        return tool_info


async def example_2_call_tools():
    """
    Example 2: Call MCP tools directly via session
    """
    print("\n" + "="*60)
    print("Example 2: Call Tools")
    print("="*60)

    async with MCPClient() as client:
        # Call tool directly via session
        print("Calling Wait-Tool...")
        result = await client.session.call_tool('Wait-Tool', {'duration': 1})

        # Extract result content
        if hasattr(result, 'content') and result.content:
            output = result.content[0].text
            print(f"Result: {output}")

        # Call another tool
        print("\nGetting clipboard content...")
        clipboard_result = await client.session.call_tool(
            'Clipboard-Tool',
            {'mode': 'paste'}
        )

        if hasattr(clipboard_result, 'content') and clipboard_result.content:
            clipboard_text = clipboard_result.content[0].text
            print(f"Clipboard: {clipboard_text[:100]}")


async def example_3_nested_pattern():
    """
    Example 3: Show the equivalent nested async with pattern
    This is what MCPClient does internally
    """
    print("\n" + "="*60)
    print("Example 3: Nested Pattern (Internal Implementation)")
    print("="*60)

    print("MCPClient internally uses this pattern:")
    print("""
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Use session here
    """)

    print("\nYou can use MCPClient as a simpler wrapper:")
    print("""
    async with MCPClient() as client:
        # Use client.session here
        tools = await client.session.list_tools()
    """)


async def example_4_convenience_methods():
    """
    Example 4: Use convenience methods (sync-style wrappers)
    """
    print("\n" + "="*60)
    print("Example 4: Convenience Methods")
    print("="*60)

    async with MCPClient() as client:
        # These methods use _run_async internally
        # So you can call them without await (but you're still in async context)

        print("Using sync-style list_tools()...")
        tools = client.list_tools()
        print(f"Found {len(tools)} tools")

        print("\nUsing sync-style call_tool()...")
        result = client.call_tool('Wait-Tool', {'duration': 1})
        print("Tool call completed")


async def example_5_error_handling():
    """
    Example 5: Proper error handling with async context manager
    """
    print("\n" + "="*60)
    print("Example 5: Error Handling")
    print("="*60)

    try:
        async with MCPClient() as client:
            print("Connected successfully")

            # Try calling a non-existent tool
            try:
                result = await client.session.call_tool('NonExistent-Tool', {})
            except Exception as e:
                print(f"Tool call error (expected): {type(e).__name__}")

            # Connection will still close properly
            print("Connection will close gracefully even after error")

    except Exception as e:
        print(f"Connection error: {e}")

    print("Client disconnected and cleaned up")


async def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("MCP Client Async Usage Examples")
    print("="*60)

    await example_1_discover_tools()
    await example_2_call_tools()
    await example_3_nested_pattern()
    await example_4_convenience_methods()
    await example_5_error_handling()

    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
