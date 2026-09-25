"""
End-to-End MCP JSON-RPC 2.0 Stdio Client Test for Preflight.
Spawns the Preflight server subprocess, executes the official MCP handshake,
inspects tool definitions, and performs real tools/call requests over stdio.
"""

import sys
import json
import subprocess
import time
from typing import Dict, Any, Optional

# Ensure UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class StdioMcpClient:
    """A minimal, compliant Model Context Protocol (MCP) JSON-RPC 2.0 client."""

    def __init__(self, command: list[str]):
        self.command = command
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0

    def start(self):
        print(f"[*] Spawning MCP server subprocess: {' '.join(self.command)}")
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
        )

    def send_raw(self, message: Dict[str, Any]):
        line = json.dumps(message) + "\n"
        self.process.stdin.write(line)
        self.process.stdin.flush()

    def receive_raw(self, timeout_sec: float = 10.0) -> Dict[str, Any]:
        start = time.time()
        while time.time() - start < timeout_sec:
            line = self.process.stdout.readline()
            if line:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    return json.loads(line_str)
                except json.JSONDecodeError:
                    # Ignore non-json logging output on stdout if any
                    continue
            time.sleep(0.02)
        raise TimeoutError("Timed out waiting for JSON-RPC response from server stdout")

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._request_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        self.send_raw(req)
        return self.receive_raw()

    def notify(self, method: str, params: Optional[Dict[str, Any]] = None):
        notif = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            notif["params"] = params
        self.send_raw(notif)

    def close(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.process.kill()


def main():
    python_exe = sys.executable
    client = StdioMcpClient([python_exe, "-m", "preflight.cli", "serve"])

    try:
        client.start()

        # Step 1: Initialize Handshake
        print("[1/4] Sending JSON-RPC 'initialize' request...")
        init_resp = client.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-mcp-client", "version": "1.0"},
        })
        print(f"      -> Response: Server name={init_resp.get('result', {}).get('serverInfo', {}).get('name')}")
        assert "result" in init_resp, f"Initialize failed: {init_resp}"
        assert init_resp["result"]["serverInfo"]["name"] == "Preflight"

        # Step 2: Send initialized notification
        print("[2/4] Sending 'notifications/initialized'...")
        client.notify("notifications/initialized")

        # Step 3: List Tools
        print("[3/4] Sending 'tools/list' request...")
        tools_resp = client.call("tools/list", {})
        tools = tools_resp.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        print(f"      -> Discovered {len(tools)} tools: {tool_names}")
        assert "verify_claim" in tool_names, "verify_claim tool not exposed!"
        assert "quick_check" in tool_names, "quick_check tool not exposed!"

        # Step 4: Execute tools/call on verify_claim with real arguments
        print("[4/4] Sending 'tools/call' for 'verify_claim' (Pydantic v2 BaseSettings)...")
        t0 = time.perf_counter()
        call_resp = client.call("tools/call", {
            "name": "verify_claim",
            "arguments": {
                "claim": "In Pydantic v2, BaseSettings is imported directly from pydantic",
                "replay": True,
            },
        })
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"      -> Completed in {elapsed_ms:.1f}ms")

        assert "result" in call_resp, f"Tool call failed: {call_resp}"
        content = call_resp["result"]["content"]
        assert len(content) > 0 and content[0]["type"] == "text"
        verdict_data = json.loads(content[0]["text"])

        print(f"      -> Structured Verdict: {verdict_data.get('verdict')} (Confidence: {verdict_data.get('confidence')})")
        print(f"      -> Recommended Fix:   {verdict_data.get('correction')}")
        print(f"      -> Canonical Doc:      {verdict_data.get('canonical_reference')}")

        assert verdict_data["verdict"] == "OUTDATED"
        assert verdict_data["is_replayed"] is True
        assert "pydantic_settings" in verdict_data["correction"]

        # Step 5: Execute quick_check tool call
        print("\n[Bonus] Sending 'tools/call' for 'quick_check' (Requests SSL verify)...")
        qc_resp = client.call("tools/call", {
            "name": "quick_check",
            "arguments": {
                "package": "requests",
                "symbol": "verify",
                "replay": True,
            },
        })
        qc_data = json.loads(qc_resp["result"]["content"][0]["text"])
        print(f"      -> QuickCheck Status: {qc_data.get('status')} (Package: {qc_data.get('package')}, Symbol: {qc_data.get('symbol')})")
        assert qc_data["status"] == "CONFIRMED"

        print("\n[SUCCESS] End-to-End MCP stdio JSON-RPC 2.0 handshake and tool execution PASSED flawlessly!")

    finally:
        client.close()


if __name__ == "__main__":
    main()
