"""Verification tests for gmail-calendar FastMCP server over stdio.

Verifies:
1. Server advertises exactly the six requested tools with clear descriptions.
2. Server handles missing token with a clear message and instructions.
3. Server communicates cleanly over stdio protocol without polluting stdout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from gmail_calendar.server import (
    check_token_status,
    mcp,
    search_emails,
    set_service_overrides,
)

EXPECTED_TOOL_NAMES = {
    "search_emails",
    "read_email",
    "create_draft",
    "list_events",
    "find_free_slots",
    "create_event",
}


@pytest.mark.asyncio
async def test_server_advertises_exactly_six_tools() -> None:
    """Verify that FastMCP server advertises exactly the six requested tools with clear descriptions."""
    tools = await mcp.list_tools()
    assert len(tools) == 6, f"Expected exactly 6 tools, but got {len(tools)}: {[t.name for t in tools]}"

    tool_names = {t.name for t in tools}
    assert tool_names == EXPECTED_TOOL_NAMES, f"Tool names mismatch: {tool_names} != {EXPECTED_TOOL_NAMES}"

    # Verify that each tool has a clear, non-empty description
    for tool in tools:
        assert tool.description is not None and len(tool.description.strip()) > 15, (
            f"Tool '{tool.name}' is missing a clear description: {tool.description}"
        )


def test_server_handles_missing_token_with_clear_message(
    temp_private_dir: Path, capsys: pytest.CaptureFixture
) -> None:
    """Verify that when token.json is missing, clear instructions are sent to stderr."""
    # Ensure overrides are cleared
    set_service_overrides(None, None)

    # Check token status reports False and logs to stderr
    status = check_token_status()
    assert status is False

    captured = capsys.readouterr()
    assert "Google OAuth token not found at" in captured.err
    assert "uv run auth --expected-email" in captured.err
    # Stdout must remain completely empty!
    assert captured.out == ""

    # Calling a tool when token is missing raises FileNotFoundError with instructions
    with pytest.raises(FileNotFoundError, match=r"(?s)Google OAuth token not found at.*uv run auth"):
        search_emails(query="test", max_results=5)


def test_server_stdio_protocol_subprocess(temp_private_dir: Path) -> None:
    """Launch the server as a subprocess over stdio and verify JSON-RPC tool listing."""
    env = os.environ.copy()
    env["GOOGLE_PRIVATE_DIR"] = str(temp_private_dir)
    # Ensure stdout is unbuffered
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [sys.executable, "-m", "gmail_calendar.server"]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        # 1. Send initialize request
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-stdio-client", "version": "1.0.0"},
            },
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()

        # Read initialize response
        init_resp_line = proc.stdout.readline()
        assert init_resp_line, "Expected initialize response from server over stdio"
        init_resp = json.loads(init_resp_line)
        assert init_resp.get("id") == 1
        assert "result" in init_resp

        # 2. Send initialized notification
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()

        # 3. Send tools/list request
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        proc.stdin.write(json.dumps(tools_req) + "\n")
        proc.stdin.flush()

        tools_resp_line = proc.stdout.readline()
        assert tools_resp_line, "Expected tools/list response from server over stdio"
        tools_resp = json.loads(tools_resp_line)
        assert tools_resp.get("id") == 2

        tools = tools_resp.get("result", {}).get("tools", [])
        assert len(tools) == 6, f"Expected 6 tools in stdio tools/list, got {len(tools)}"
        names = {t["name"] for t in tools}
        assert names == EXPECTED_TOOL_NAMES

    finally:
        proc.terminate()
        try:
            _, stderr_output = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr_output = proc.communicate()

        # Check that diagnostics went to stderr
        assert "gmail-calendar" in stderr_output
