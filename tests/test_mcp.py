"""Chunk 2 — P1 MCP stdio server: tools check / history / report.

Calls the tool handlers directly (no spawned MCP process). The handlers
themselves run the engine as a subprocess — that is the specified contract.
"""

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from falsify_agent import ledger
from falsify_agent.mcp_server import (
    EngineError,
    build_server,
    tool_check,
    tool_history,
    tool_report,
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("FALSIFY_HOME", str(tmp_path / ".falsify"))
    return tmp_path / ".falsify"


@pytest.fixture
def csvs(tmp_path):
    """Two trade sets with different canonical hashes."""
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    shutil.copy(REPO / "examples" / "known_good.csv", a)
    shutil.copy(REPO / "examples" / "known_overfit.csv", b)
    return a, b


def test_check_logs_declared_and_counts_observed(home, csvs):
    a, b = csvs
    r1 = tool_check(str(a), "ema", params=2, trials=1)
    assert r1["run"] == 1
    assert r1["trials"] == {"declared": 1, "observed": 1, "used_for_deflated": 1}
    assert r1["verdict"]["deflated"] is None
    assert r1["deflated_checks"] is None
    assert r1["record"]["verdict"] == r1["verdict"]["declared"]

    r2 = tool_check(str(b), "ema", params=2, trials=1)
    assert r2["run"] == 2
    assert r2["trials"]["observed"] == 2
    # observed > declared → second engine pass, deflated verdict shown...
    assert r2["verdict"]["deflated"] is not None
    assert r2["deflated_checks"] is not None
    assert r2["trials"]["used_for_deflated"] == 2
    # ...but not logged: still 2 runs, observed still 2
    assert ledger.status("ema")["runs"] == 2
    assert ledger.observed_trials("ema") == 2


def test_check_requires_strategy(home, csvs):
    with pytest.raises(ValueError, match="strategy is required"):
        tool_check(str(csvs[0]), "", params=2)


def test_check_engine_error_not_logged(home, tmp_path):
    with pytest.raises(EngineError, match="Error:"):
        tool_check(str(tmp_path / "missing.csv"), "ema", params=2)
    assert ledger.status("ema") is None


def test_history_newest_first(home, csvs):
    a, b = csvs
    tool_check(str(a), "ema", params=2, trials=1)
    tool_check(str(b), "ema", params=2, trials=1)
    h = tool_history("ema")
    assert h["observed_trials"] == 2
    assert h["runs"] == 2  # integer count, same key as status --json
    assert [e["run"] for e in h["entries"]] == [2, 1]
    entry = h["entries"][0]
    assert set(entry) == {"run", "created_at", "verdict",
                          "declared_trials", "canonical_sha256"}
    assert len(entry["canonical_sha256"]) == 12
    assert tool_history("ema", limit=1)["entries"] == h["entries"][:1]


def test_history_unknown_strategy(home):
    with pytest.raises(ValueError, match='ยังไม่มี run'):
        tool_history("nope")


def test_report_builds_html_file(home, csvs):
    with pytest.raises(ValueError, match='ยังไม่มี run'):
        tool_report("ema")
    tool_check(str(csvs[0]), "ema", params=2, trials=1)
    out = tool_report("ema")
    assert out["path"] is not None
    assert Path(out["path"]).exists()
    assert "http" not in Path(out["path"]).read_text(encoding="utf-8")


def test_server_lists_three_tools(home):
    tools = asyncio.run(build_server().list_tools())
    assert sorted(t.name for t in tools) == ["check", "history", "report"]


def test_base_install_has_no_mcp_dep():
    text = (REPO / "pyproject.toml").read_text()
    main_deps = text.split("[project.optional-dependencies]")[0]
    assert "mcp" not in main_deps
    assert 'mcp = ["mcp>=2.2,<2.3"]' in text


def test_cli_and_ledger_import_without_mcp():
    code = "import sys; sys.modules['mcp'] = None; sys.modules['mcp.server'] = None; " \
        "sys.modules['mcp.server.mcpserver'] = None; " \
        "import falsify_agent.cli, falsify_agent.ledger; print('ok')"
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout


def test_mcp_entrypoint_needs_extra_without_it():
    code = "import sys; sys.modules['mcp'] = None; " \
        "sys.modules['mcp.server'] = None; " \
        "sys.modules['mcp.server.mcpserver'] = None; " \
        "from falsify_agent.cli import cmd_mcp; sys.exit(cmd_mcp())"
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 2
    assert "[mcp]" in r.stderr
