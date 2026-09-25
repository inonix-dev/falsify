"""P1 install — write MCP client configs (stdlib only, base install).

- claude-desktop (macOS): merge ``mcpServers.falsify`` into
  ``~/Library/Application Support/Claude/claude_desktop_config.json``
- cursor: merge into ``~/.cursor/mcp.json``
- claude-code: print the ``claude mcp add ...`` command for the user to run

Merge never touches other keys; a ``<file>.bak`` is written before every edit.
Broken existing JSON → stop, report the path, change nothing.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path

SERVER_KEY = "falsify"

CLIENTS = (
    "claude-desktop",
    "claude-code",
    "cursor",
)


class ConfigError(RuntimeError):
    """Existing config exists but cannot be parsed — nothing was changed."""


def client_path(client: str) -> Path | None:
    home = Path.home()
    if client == "claude-desktop":
        return (home / "Library/Application Support/Claude"
                / "claude_desktop_config.json")
    if client == "cursor":
        return home / ".cursor" / "mcp.json"
    if client == "claude-code":
        return None
    raise ValueError(f"unknown client: {client} (choose from {', '.join(CLIENTS)})")


def server_entry() -> dict:
    """How a client should launch us. Absolute path, no PATH guessing."""
    cmd = shutil.which("falsify-agent")
    if cmd is not None:
        return {"command": os.path.abspath(cmd), "args": ["mcp"]}
    return {"command": sys.executable,
            "args": ["-m", "falsify_agent.cli", "mcp"]}


def claude_code_command() -> str:
    entry = server_entry()
    return shlex.join(["claude", "mcp", "add", SERVER_KEY, "--",
                       entry["command"], *entry["args"]])


def install_file_config(path: Path) -> Path:
    """Merge ``mcpServers.falsify`` into a JSON config file. Returns the path."""
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        raise ConfigError(f"{path} อ่านไม่ได้ (JSON พัง) — ไม่แก้อะไร")
    if not isinstance(current, dict):
        raise ConfigError(f"{path} ไม่ใช่ JSON object — ไม่แก้อะไร")
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    servers = current.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ConfigError(f"{path}: mcpServers ไม่ใช่ object — ไม่แก้อะไร")
    servers[SERVER_KEY] = server_entry()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def install(client: str) -> str:
    """Install for one client. Returns a human-readable result line."""
    if client == "claude-code":
        return claude_code_command()
    path = client_path(client)
    assert path is not None
    install_file_config(path)
    return f"wrote {path}"
