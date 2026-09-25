"""
Unit tests for Preflight client installer and CLI init command.
Verifies multi-OS path resolution, non-destructive JSON merging,
and conflict detection across Claude Code, Claude Desktop, Cursor, and OpenCode.
"""

import os
import sys
import json
import pytest
from pathlib import Path

from preflight.client_installer import (
    get_config_path,
    merge_config_data,
    install_client,
    resolve_executable_command,
    ClientConfigConflictError,
    SUPPORTED_CLIENTS,
)


def test_supported_clients_list():
    assert "claude-code" in SUPPORTED_CLIENTS
    assert "claude-desktop" in SUPPORTED_CLIENTS
    assert "cursor" in SUPPORTED_CLIENTS
    assert "opencode" in SUPPORTED_CLIENTS


def test_resolve_executable_command():
    cmd, args = resolve_executable_command()
    assert isinstance(cmd, str)
    assert len(cmd) > 0
    assert isinstance(args, list)
    assert len(args) > 0


def test_get_config_path_cursor(tmp_path):
    proj_path = get_config_path("cursor", is_global=False, project_dir=tmp_path)
    assert proj_path == tmp_path / ".cursor" / "mcp.json"

    global_path = get_config_path("cursor", is_global=True, home_dir=tmp_path)
    assert global_path == tmp_path / ".cursor" / "mcp.json"


def test_get_config_path_claude_code(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    p = get_config_path("claude-code", home_dir=tmp_path)
    assert p == tmp_path / ".claude.json"

    # Custom CLAUDE_CONFIG_DIR
    custom_dir = tmp_path / "custom_claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_dir))
    p_custom = get_config_path("claude-code", home_dir=tmp_path)
    assert p_custom == custom_dir / ".claude.json"


def test_get_config_path_claude_desktop_platforms(tmp_path, monkeypatch):
    # Windows
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    p_win = get_config_path("claude-desktop", home_dir=tmp_path)
    assert "Claude" in str(p_win)
    assert p_win.name == "claude_desktop_config.json"

    # macOS (Darwin)
    monkeypatch.setattr(sys, "platform", "darwin")
    p_mac = get_config_path("claude-desktop", home_dir=tmp_path)
    assert str(p_mac) == str(tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")

    # Linux
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    p_linux = get_config_path("claude-desktop", home_dir=tmp_path)
    assert str(p_linux) == str(tmp_path / ".config" / "Claude" / "claude_desktop_config.json")


def test_get_config_path_opencode(tmp_path):
    # Default project path without .opencode folder
    p = get_config_path("opencode", is_global=False, project_dir=tmp_path)
    assert p == tmp_path / "opencode.json"

    # Project path with .opencode folder
    (tmp_path / ".opencode").mkdir()
    p_dot = get_config_path("opencode", is_global=False, project_dir=tmp_path)
    assert p_dot == tmp_path / ".opencode" / "opencode.json"


def test_install_client_creates_new_file(tmp_path):
    res = install_client(
        client="cursor",
        project_dir=tmp_path,
        command_override="preflight",
        args_override=["serve"],
    )

    assert res.action == "CREATED"
    assert res.config_path.exists()

    with open(res.config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "mcpServers" in data
    assert "preflight" in data["mcpServers"]
    assert data["mcpServers"]["preflight"]["command"] == "preflight"
    assert data["mcpServers"]["preflight"]["args"] == ["serve"]


def test_install_client_merges_without_clobbering(tmp_path):
    config_file = tmp_path / ".cursor" / "mcp.json"
    config_file.parent.mkdir(parents=True)

    initial_data = {
        "theme": "dark",
        "mcpServers": {
            "existing-tool": {
                "command": "node",
                "args": ["server.js"]
            }
        }
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f)

    res = install_client(
        client="cursor",
        project_dir=tmp_path,
        command_override="preflight",
        args_override=["serve"],
    )

    assert res.action == "CREATED"
    with open(config_file, "r", encoding="utf-8") as f:
        merged = json.load(f)

    # Top-level key preserved
    assert merged["theme"] == "dark"
    # Existing tool preserved
    assert "existing-tool" in merged["mcpServers"]
    assert merged["mcpServers"]["existing-tool"]["command"] == "node"
    # New server added
    assert "preflight" in merged["mcpServers"]


def test_install_client_conflict_and_force(tmp_path):
    config_file = tmp_path / ".cursor" / "mcp.json"
    config_file.parent.mkdir(parents=True)

    initial_data = {
        "mcpServers": {
            "preflight": {
                "command": "old-command",
                "args": []
            }
        }
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f)

    # Conflict without force
    with pytest.raises(ClientConfigConflictError):
        install_client(
            client="cursor",
            project_dir=tmp_path,
            force=False,
        )

    # Success with force
    res = install_client(
        client="cursor",
        project_dir=tmp_path,
        command_override="preflight",
        args_override=["serve"],
        force=True,
    )
    assert res.action == "UPDATED"

    with open(config_file, "r", encoding="utf-8") as f:
        updated = json.load(f)

    assert updated["mcpServers"]["preflight"]["command"] == "preflight"


def test_install_client_prunes_legacy_fact_dock(tmp_path):
    config_file = tmp_path / ".cursor" / "mcp.json"
    config_file.parent.mkdir(parents=True)

    initial_data = {
        "mcpServers": {
            "fact-dock": {
                "command": "old-fact-dock-command",
                "args": ["serve"]
            }
        }
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f)

    res = install_client(
        client="cursor",
        project_dir=tmp_path,
        command_override="preflight",
        args_override=["serve"],
    )
    assert res.action == "CREATED"

    with open(config_file, "r", encoding="utf-8") as f:
        updated = json.load(f)

    assert "preflight" in updated["mcpServers"]
    assert "fact-dock" not in updated["mcpServers"]


def test_opencode_native_mcp_format_merge(tmp_path):
    config_file = tmp_path / "opencode.json"
    initial_data = {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {
            "other-mcp": {"type": "local", "command": ["npx", "server"], "enabled": True}
        }
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f)

    res = install_client(
        client="opencode",
        project_dir=tmp_path,
        command_override="preflight",
        args_override=["serve"],
    )

    with open(config_file, "r", encoding="utf-8") as f:
        merged = json.load(f)

    assert "mcp" in merged
    assert "preflight" in merged["mcp"]
    assert merged["mcp"]["preflight"]["type"] == "local"
    assert merged["mcp"]["preflight"]["command"] == ["preflight", "serve"]
    assert "other-mcp" in merged["mcp"]

