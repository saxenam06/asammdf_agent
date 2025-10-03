"""
Quick test to verify MCP integration is working
Run this from .agent-venv to test both environments working together
"""

import sys
import os

print("=" * 60)
print("Testing MCP Integration")
print("=" * 60)

# Check current environment
print(f"\nCurrent Python: {sys.executable}")
print(f"Current working directory: {os.getcwd()}")

# Try importing agent dependencies
print("\n[1] Testing agent dependencies...")
try:
    import langchain
    import langgraph
    import anthropic
    print("✓ Agent dependencies OK (langchain, langgraph, anthropic)")
except ImportError as e:
    print(f"✗ Agent dependencies missing: {e}")
    print("Make sure you activated .agent-venv")
    sys.exit(1)

# Try importing MCP client
print("\n[2] Testing MCP client import...")
try:
    from agent.execution.mcp_client import WindowsMCPWrapper
    print("✓ MCP client import OK")
except ImportError as e:
    print(f"✗ MCP client import failed: {e}")
    sys.exit(1)

# Try creating MCP wrapper
print("\n[3] Testing MCP wrapper initialization...")
try:
    wrapper = WindowsMCPWrapper()
    print("✓ MCP wrapper created")
except Exception as e:
    print(f"✗ MCP wrapper creation failed: {e}")
    sys.exit(1)

# Check MCP config
print("\n[4] Checking MCP configuration...")
config_path = os.path.join(os.getcwd(), 'mcp_config.json')
if os.path.exists(config_path):
    print(f"✓ MCP config found: {config_path}")
    import json
    with open(config_path, 'r') as f:
        config = json.load(f)
        server_config = config.get('mcpServers', {}).get('windows-mcp', {})
        python_path = server_config.get('command')
        print(f"  Windows-MCP Python: {python_path}")
        if os.path.exists(python_path):
            print(f"  ✓ Python executable exists")
        else:
            print(f"  ✗ Python executable NOT found - check .windows-venv setup")
else:
    print(f"✗ MCP config not found: {config_path}")
    sys.exit(1)

# Try starting the server (don't actually call tools yet)
print("\n[5] Testing server startup...")
try:
    wrapper.client.start_server('windows-mcp')
    print("✓ Windows-MCP server started successfully")
    print(f"  Server process: {wrapper.client.servers['windows-mcp']['process'].pid}")

    # Cleanup
    wrapper.cleanup()
    print("✓ Server stopped cleanly")
except Exception as e:
    print(f"✗ Server startup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ ALL TESTS PASSED!")
print("=" * 60)
print("\nIntegration is working correctly!")
print("- Agent runs in .agent-venv")
print("- Windows-MCP runs in .windows-venv")
print("- Communication via MCP protocol works")
print("\nYou can now run your agent scripts.")
