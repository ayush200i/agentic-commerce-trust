"""Development MCP bridge: loads ignored test credentials and forwards to the official remote server.

The shipped FastAPI runtime calls that same official remote server directly through the MCP SDK.
No Razorpay REST or payments SDK wrapper is used.
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from backend.providers import ProviderError, RazorpayMCP

server = Server("counterseal-razorpay-test")
remote = RazorpayMCP()


@server.list_tools()
async def list_tools():
    result = await remote.discover()
    return [Tool.model_validate(t) for t in result["tool_schemas"]]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    # This developer bridge has test-key and tool restrictions. Product checkout goes through Commerce.
    try:
        result = await remote.call(name, arguments)
        return [TextContent(type="text", text=json.dumps(result))]
    except ProviderError as error:
        raise ValueError(str(error)) from None


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
