"""
Direct MCP client for Burr workflows.
Connects to brightwheel_mcp.py without LLM orchestration.
"""

import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pathlib import Path

MCP_SERVER_PATH = str(Path(__file__).parent.parent / "tools" / "brightwheel_mcp.py")


async def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """
    Direct MCP call - NO LLM in the loop.

    PRODUCTION SWAP:
    - stdio_server() → SSE client for remote MCP server
    - Add connection pooling for concurrent requests
    """
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.tools.brightwheel_mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return json.loads(result.content[0].text)


def parse_time(time_str: str) -> int | None:
    """
    Convert 'HH:MM' or 'H:MM' to minutes since midnight.
    Used for deterministic time comparison.
    """
    if not time_str:
        return None
    try:
        # Strip AM/PM (all times are in 24h format in our data)
        clean = time_str.strip().replace("AM", "").replace("PM", "").strip()
        parts = clean.split(":")
        hours, minutes = int(parts[0]), int(parts[1])
        return hours * 60 + minutes
    except (ValueError, IndexError, AttributeError):
        return None
