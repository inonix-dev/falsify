"""CLI for the agent-side package: ``falsify-agent log`` / ``status``.

Base install, stdlib only. Reads engine JSON records from stdin (``log``) or
the ledger file (``status``). Never produces or alters verdicts.
"""

from __future__ import annotations

import argparse
import json
import sys

from falsify_agent import ledger


def _date(value) -> str:
    return value[:10] if isinstance(value, str) else "?"


def cmd_log() -> int:
    try:
        record = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print("falsify-agent log: stdin ไม่ใช่ JSON", file=sys.stderr)
        return 2
    if not isinstance(record, dict) or record.get("schema_version") != ledger.SCHEMA_VERSION:
        print(
            f"falsify-agent log: ต้องเป็น engine record schema_version {ledger.SCHEMA_VERSION}",
            file=sys.stderr,
        )
        return 2
    ledger.append_record(record)
    strategy = ledger._strategy_of(record)
    if strategy is None:
        print("จดแล้ว (ไม่มี --strategy — ไม่นับ trial)")
        return 0
    declared = record.get("declared", {}).get("trials")
    observed = ledger.observed_trials(strategy)
    print(f"{strategy}: กรอก --trials {declared} · ledger นับได้ {observed}")
    return 0


def cmd_status(strategy: str, as_json: bool) -> int:
    summary = ledger.status(strategy)
    if summary is None:
        print(f'ยังไม่มี run ของ "{strategy}"', file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    verdicts = summary["verdicts"]
    parts = [f"{v} ×{verdicts[v]}" for v in ledger.VERDICTS if verdicts[v]]
    print(
        f"{strategy} — {summary['runs']} runs "
        f"· {_date(summary['first_at'])} → {_date(summary['last_at'])}"
    )
    print(
        f"  trials: กรอก --trials {summary['last_declared_trials']} "
        f"· ledger นับได้ {summary['observed_trials']}"
    )
    print(
        f"  verdict: {' · '.join(parts)} "
        f"(run #{summary['runs']}, หลังลอง {summary['observed_trials']} แบบ)"
    )
    return 0


def cmd_mcp() -> int:
    try:
        from falsify_agent import mcp_server
        mcp_server.main()
    except ImportError:
        print(
            "falsify-agent mcp ต้องการ extra [mcp]: pip install falsify-backtest[mcp]",
            file=sys.stderr,
        )
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="falsify-agent",
        description="Agent-side ledger for falsify engine records.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("log", help="Read an engine JSON record from stdin, append to ledger")

    st = sub.add_parser("status", help="Show declared vs observed trials for a strategy")
    st.add_argument("strategy", help="Strategy name (exact match)")
    st.add_argument("--json", action="store_true", help="Machine-readable output")

    sub.add_parser("mcp", help="Serve the MCP stdio server (needs extra [mcp])")

    ins = sub.add_parser("install", help="Register falsify in an MCP client config")
    ins.add_argument("--client", required=True,
                     choices=["claude-desktop", "claude-code", "cursor"])
    return parser


def cmd_install(client: str) -> int:
    from falsify_agent import install
    try:
        print(install.install(client))
    except install.ConfigError as exc:
        print(f"falsify-agent install: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "log":
        code = cmd_log()
    elif args.command == "status":
        code = cmd_status(args.strategy, args.json)
    elif args.command == "mcp":
        code = cmd_mcp()
    elif args.command == "install":
        code = cmd_install(args.client)
    else:  # pragma: no cover — argparse required=True guards this
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
