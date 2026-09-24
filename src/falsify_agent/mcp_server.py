"""P1 MCP stdio server — tools check / history / report.

Requires the ``[mcp]`` extra. The engine is called as a subprocess
(``sys.executable -m falsify.cli``) so the only contract with it is the
public JSON record — never imported.

``check`` return shape is additive-only: new keys (e.g. the junior layer's
``guidance``) may be added later without breaking existing clients.
"""

from __future__ import annotations

import json
import subprocess
import sys

from falsify_agent import ledger

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # pragma: no cover — exercised via `falsify-agent mcp` without extra
    MCPServer = None  # type: ignore[assignment,misc]

ENGINE_TIMEOUT = 120


class EngineError(RuntimeError):
    """Engine refused the input — message is the engine's stderr, verbatim."""


def run_engine(csv_path: str, strategy: str, params: int,
               trials: int, input_format: str | None = None) -> dict:
    """Run the engine once, return its JSON record.

    Exit 0 (pass) and 1 (fail) are both normal. Anything else — unparseable
    stdout, ``Error:`` on stderr — raises EngineError and logs nothing.
    """
    cmd = [sys.executable, "-m", "falsify.cli", "check", csv_path,
           "--params", str(params), "--trials", str(trials),
           "--strategy", strategy, "--json"]
    if input_format is not None:
        cmd += ["--from", input_format]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=ENGINE_TIMEOUT)
    try:
        record = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise EngineError(proc.stderr.strip() or f"engine exit {proc.returncode}")
    if not isinstance(record, dict) or record.get("schema_version") != ledger.SCHEMA_VERSION:
        raise EngineError(proc.stderr.strip() or "engine returned an unknown record")
    return record


def tool_check(csv_path: str, strategy: str, params: int,
               trials: int = 1, input_format: str | None = None) -> dict:
    """Check a trade CSV, logging declared trials and deflating with observed."""
    if not strategy:
        raise ValueError("strategy is required (ledger cannot count unnamed runs)")
    record = run_engine(csv_path, strategy, params, trials, input_format)
    ledger.append_record(record)
    summary = ledger.status(strategy)
    assert summary is not None  # just appended
    observed = summary["observed_trials"]
    used = max(trials, observed)
    deflated_verdict = None
    deflated_checks = None
    if observed > trials:
        # Second pass, NOT logged — it re-judges the same input, not a new trial.
        rerecord = run_engine(csv_path, strategy, params, observed, input_format)
        deflated_verdict = rerecord["verdict"]
        deflated_checks = rerecord["checks"]
    return {
        "run": summary["runs"],
        "strategy": strategy,
        "trials": {"declared": trials, "observed": observed,
                   "used_for_deflated": used},
        "verdict": {"declared": record["verdict"], "deflated": deflated_verdict},
        "record": record,
        "deflated_checks": deflated_checks,
        # Reserved for the junior guidance layer (PLAN-cloud-v0-ledger §8.5):
        # additive key, None until that chunk ships.
        "guidance": None,
        "report_path": None,  # chunk 4 (HTML) fills this in
    }


def tool_history(strategy: str, limit: int = 20) -> dict:
    """Ledger summary + newest-first run list for one strategy."""
    summary = ledger.status(strategy)
    if summary is None:
        raise ValueError(f'ยังไม่มี run ของ "{strategy}"')
    runs = ledger.strategy_runs(strategy)
    total = len(runs)
    entries = []
    for i in range(total - 1, max(total - limit, 0) - 1, -1):
        record = runs[i]
        sha = record.get("input", {}).get("canonical_sha256")
        entries.append({
            "run": i + 1,
            "created_at": record.get("created_at"),
            "verdict": record.get("verdict"),
            "declared_trials": record.get("declared", {}).get("trials"),
            "canonical_sha256": sha[:12] if isinstance(sha, str) else None,
        })
    return {**summary, "runs": entries}


def tool_report(strategy: str, run: int | None = None) -> dict:
    """HTML report path for a run (latest when run is None). Chunk 4 builds it."""
    return {"path": None}


def build_server() -> "MCPServer":
    if MCPServer is None:  # pragma: no cover — only without the [mcp] extra
        raise ImportError("the [mcp] extra is not installed")
    server = MCPServer("falsify")

    @server.tool()
    def check(csv_path: str, strategy: str, params: int,
              trials: int = 1, input_format: str | None = None) -> dict:
        """Run falsify checks on a trade CSV. strategy is required."""
        return tool_check(csv_path, strategy, params, trials, input_format)

    @server.tool()
    def history(strategy: str, limit: int = 20) -> dict:
        """Past runs and declared-vs-observed trials for a strategy."""
        return tool_history(strategy, limit)

    @server.tool()
    def report(strategy: str, run: int | None = None) -> dict:
        """HTML report path for a run (latest when omitted)."""
        return tool_report(strategy, run)

    return server


def main() -> None:
    """Serve stdio. `falsify-agent mcp` calls this (extra [mcp] required)."""
    build_server().run()


if __name__ == "__main__":
    main()
