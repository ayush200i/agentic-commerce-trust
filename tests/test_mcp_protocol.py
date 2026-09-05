import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from backend.providers import ProviderError, RazorpayMCP


async def test_official_sdk_discovery_schema_validation_and_tool_call(monkeypatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("mcp_fixture.py")), str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fixture")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "fixture-only")
    client = RazorpayMCP()
    client.URL = f"http://127.0.0.1:{port}/mcp"
    try:
        async with httpx.AsyncClient() as http:
            for _ in range(60):
                try:
                    await http.get(client.URL, timeout=0.3)
                    break
                except httpx.TransportError:
                    await asyncio.sleep(0.1)
            else:
                pytest.fail("Local MCP fixture did not start")
        assert (await client.discover())["tools"] == ["create_order"]
        response = await client.call(
            "create_order", {"amount": 12000, "currency": "INR", "receipt": "protocol-test"}
        )
        assert response["amount"] == 12000
        assert response["id"] == "order_protocol"
        with pytest.raises(ProviderError):
            await client.call("create_order", {"currency": "INR"})
        with pytest.raises(ProviderError):
            await client.call("create_refund", {})
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
