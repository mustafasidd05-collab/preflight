"""
Automated Pytest for End-to-End FastMCP Server over real stdio JSON-RPC.
"""

import sys
import json
from pathlib import Path
import pytest

# Ensure workspace root is in sys.path
workspace_root = str(Path(__file__).parent.parent)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from demo.test_mcp_client import StdioMcpClient


def test_mcp_stdio_handshake_and_tool_call():
    python_exe = sys.executable
    client = StdioMcpClient([python_exe, "-m", "preflight.cli", "serve"])

    try:
        client.start()

        # 1. Initialize
        init_resp = client.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest-mcp-client", "version": "1.0"},
        })
        assert "result" in init_resp
        assert init_resp["result"]["serverInfo"]["name"] == "Preflight"

        # 2. Initialized notification
        client.notify("notifications/initialized")

        # 3. List tools
        tools_resp = client.call("tools/list", {})
        tool_names = [t["name"] for t in tools_resp.get("result", {}).get("tools", [])]
        assert "verify_claim" in tool_names
        assert "quick_check" in tool_names

        # 4. Call verify_claim tool over stdio
        call_resp = client.call("tools/call", {
            "name": "verify_claim",
            "arguments": {
                "claim": "In Pydantic v2, BaseSettings is imported directly from pydantic",
                "replay": True,
            },
        })
        assert "result" in call_resp
        content = call_resp["result"]["content"]
        assert len(content) > 0
        verdict = json.loads(content[0]["text"])

        assert verdict["verdict"] == "OUTDATED"
        assert verdict["is_replayed"] is True
        assert "pydantic_settings" in (verdict.get("correction") or "")

        # 5. Call quick_check tool over stdio
        qc_resp = client.call("tools/call", {
            "name": "quick_check",
            "arguments": {
                "package": "requests",
                "symbol": "verify",
                "replay": True,
            },
        })
        assert "result" in qc_resp
        qc_data = json.loads(qc_resp["result"]["content"][0]["text"])
        assert qc_data["status"] == "CONFIRMED"

    finally:
        client.close()
