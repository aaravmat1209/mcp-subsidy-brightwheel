"""
MCP Connection Pool - Single long-running server

Mirrors mcp-atlassian architecture:
- Spawns ONE subprocess that stays alive
- All tool calls reuse the same connection
- Connection initialized once in module scope

This eliminates the 1.4s subprocess overhead per call!
"""

import json
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Optional

# Global connection pool
_mcp_session: Optional[ClientSession] = None
_mcp_read = None
_mcp_write = None
_mcp_client_context = None


async def initialize_mcp_pool():
    """Initialize the MCP connection pool (call once at startup)."""
    global _mcp_session, _mcp_read, _mcp_write, _mcp_client_context

    if _mcp_session is not None:
        return  # Already initialized

    print("[MCP Pool] Starting long-running MCP server...")

    # Get absolute path to the MCP server
    from pathlib import Path
    mcp_server_path = Path(__file__).parent.parent / "tools" / "brightwheel_mcp_fastmcp.py"

    server_params = StdioServerParameters(
        command="python",
        args=[str(mcp_server_path)]
    )

    # Create the stdio_client context manager
    _mcp_client_context = stdio_client(server_params)
    _mcp_read, _mcp_write = await _mcp_client_context.__aenter__()

    # Create session
    _mcp_session = ClientSession(_mcp_read, _mcp_write)
    await _mcp_session.__aenter__()

    # Initialize the session
    await _mcp_session.initialize()

    print("[MCP Pool] Server initialized and ready!")


async def shutdown_mcp_pool():
    """Shutdown the MCP connection pool (call at app shutdown)."""
    global _mcp_session, _mcp_client_context

    if _mcp_session:
        print("[MCP Pool] Shutting down MCP server...")
        await _mcp_session.__aexit__(None, None, None)
        await _mcp_client_context.__aexit__(None, None, None)
        _mcp_session = None


async def call_mcp_tool_pooled(tool_name: str, arguments: dict) -> dict:
    """
    Call MCP tool using the connection pool.

    This reuses the same subprocess, eliminating 1.4s overhead!
    """
    global _mcp_session

    if _mcp_session is None:
        await initialize_mcp_pool()

    result = await _mcp_session.call_tool(tool_name, arguments)
    return json.loads(result.content[0].text)


# For backwards compatibility
async def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Backwards compatible function - redirects to pooled version."""
    return await call_mcp_tool_pooled(tool_name, arguments)


def parse_time(time_str: str) -> int | None:
    """Convert 'HH:MM' or 'H:MM' to minutes since midnight."""
    if not time_str:
        return None
    try:
        clean = time_str.strip().replace("AM", "").replace("PM", "").strip()
        parts = clean.split(":")
        hours, minutes = int(parts[0]), int(parts[1])
        return hours * 60 + minutes
    except (ValueError, IndexError, AttributeError):
        return None
