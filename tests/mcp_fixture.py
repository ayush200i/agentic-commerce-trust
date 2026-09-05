"""Local protocol fixture; never calls Razorpay or moves money."""

import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test-payment-tools", host="127.0.0.1", port=int(sys.argv[1]), log_level="ERROR")


@mcp.tool()
def create_order(amount: int, currency: str, receipt: str) -> dict:
    return {
        "id": "order_protocol",
        "amount": amount,
        "currency": currency,
        "receipt": receipt,
        "status": "created",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
