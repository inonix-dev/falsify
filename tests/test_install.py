"""Chunk 3 — P1 install: client configs + .mcpb manifest."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from falsify_agent import install

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_claude_desktop_merge(home):
    out = install.install("claude-desktop")
    path = Path(out.removeprefix("wrote "))
    entry = read(path)["mcpServers"]["falsify"]
    assert entry["args"][-1] == "mcp"
    assert Path(entry["command"]).is_absolute()


def test_merge_preserves_other_keys_and_backs_up(home):
    target = install.client_path("claude-desktop")
    assert target is not None
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"mcpServers": {"other": {"command": "x", "args": []}}}),
                      encoding="utf-8")
    install.install("claude-desktop")
    merged = read(target)["mcpServers"]
    assert set(merged) == {"other", "falsify"}
    assert read(target.with_suffix(".json.bak"))["mcpServers"] == {"other": {"command": "x", "args": []}}


def test_broken_json_stops_without_changes(home):
    target = install.client_path("cursor")
    assert target is not None
    target.parent.mkdir(parents=True)
    target.write_text("{broken", encoding="utf-8")
    with pytest.raises(install.ConfigError, match=str(target)):
        install.install("cursor")
    assert target.read_text(encoding="utf-8") == "{broken"
    assert not target.with_suffix(".json.bak").exists()


def test_claude_code_prints_command(home, capsys):
    assert install.install("claude-code").startswith("claude mcp add falsify -- ")


def test_server_entry_prefers_path_executable(monkeypatch):
    monkeypatch.setattr(install.shutil, "which", lambda _: "/usr/local/bin/falsify-agent")
    assert install.server_entry() == {"command": "/usr/local/bin/falsify-agent", "args": ["mcp"]}


def test_server_entry_falls_back_to_module(monkeypatch):
    monkeypatch.setattr(install.shutil, "which", lambda _: None)
    entry = install.server_entry()
    assert entry == {"command": sys.executable,
                     "args": ["-m", "falsify_agent.cli", "mcp"]}


def test_manifest_contract():
    manifest = json.loads((REPO / "mcpb" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["server"]["type"] == "python"
    assert manifest["server"]["entry_point"] == "falsify_agent/mcp_server.py"
    assert {t["name"] for t in manifest["tools"]} == {"check", "history", "report"}


def test_cli_install_end_to_end(home):
    r = subprocess.run([sys.executable, "-m", "falsify_agent.cli",
                        "install", "--client", "cursor"],
                       capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stderr
    assert "falsify" in read(Path(r.stdout.removeprefix("wrote ").strip()))["mcpServers"]
