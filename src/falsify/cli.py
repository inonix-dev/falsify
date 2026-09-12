"""CLI entry point for falsify."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from falsify import __version__
from falsify.checks import (
    CheckResult,
    Verdict,
    deflated_sharpe,
    param_overfit_ratio,
    sample_size,
    worst_verdict,
)
from falsify.adapters import ADAPTERS
from falsify.io import load_trades


@dataclass
class RunResult:
    results: list[CheckResult]
    sharpe: float
    skew: float
    kurtosis: float


def _json_safe(value):
    """Coerce non-finite floats to None so the record stays strict JSON.

    pandas skew/kurtosis return NaN on degenerate inputs (e.g. n<3);
    json.dumps would emit bare NaN/Infinity, which RFC 8259 rejects and
    strict consumers (jq, the cloud layer) refuse to parse.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


def _result_to_dict(r: CheckResult) -> dict:
    d = {
        "name": r.name,
        "verdict": r.verdict.value,
        "value": _json_safe(r.value),
        "threshold": r.threshold,
        "explanation": r.explanation,
    }
    if r.inputs is not None:
        d["inputs"] = _json_safe(r.inputs)
    return d


def _compute_sharpe(trades: pd.DataFrame) -> float:
    """Compute annualised Sharpe ratio from trades (returns = pnl / mean_abs_pnl)."""
    pnl = trades["pnl"].values
    mu = np.mean(np.abs(pnl))
    if mu == 0:
        return 0.0
    returns = pnl / mu
    std = np.std(returns, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(returns) / std)


def _compute_skew_kurtosis(trades: pd.DataFrame) -> tuple[float, float]:
    """Compute skewness and excess kurtosis of trade returns."""
    pnl = trades["pnl"].values
    mu = np.mean(np.abs(pnl))
    if mu == 0:
        return 0.0, 3.0  # excess kurtosis of normal = 0, but return 3 for raw kurtosis
    returns = pnl / mu
    skew = float(pd.Series(returns).skew())
    kurt = float(pd.Series(returns).kurtosis())  # pandas kurtosis = excess kurtosis
    return skew, kurt


def run_checks(
    trades: pd.DataFrame,
    n_params: int,
    n_trials: int,
) -> RunResult:
    """Run all three checks and return results with computed stats."""
    n_trades = len(trades)
    n_wins = int((trades["pnl"] > 0).sum())

    skew, kurt = _compute_skew_kurtosis(trades)
    sharpe = _compute_sharpe(trades)

    results: list[CheckResult] = []

    # 1. Sample size
    results.append(sample_size(n_trades, n_wins))

    # 2. Deflated Sharpe
    results.append(deflated_sharpe(sharpe, n_trades, n_trials, skew, kurt))

    # 3. Param overfit ratio
    results.append(param_overfit_ratio(n_trades, n_params))

    return RunResult(results=results, sharpe=sharpe, skew=skew, kurtosis=kurt)


def _build_overall_explanation(
    results: list[CheckResult],
    n_params: int,
    n_trials: int,
    trials_was_default: bool,
) -> str:
    """Build a human-readable summary line."""
    overall = worst_verdict(results)
    parts = [f"Overall: {overall.value}"]

    if trials_was_default and overall != Verdict.pass_:
        parts.append(
            "(--trials not set, defaulting to 1 — real overfitting risk likely higher)"
        )

    return " ".join(parts)


def _print_human_report(
    results: list[CheckResult],
    n_trades: int,
    n_params: int,
    n_trials: int,
    trials_was_default: bool,
    passthrough: dict[str, str | None] | None = None,
    date_range: dict[str, str] | None = None,
) -> None:
    overall = worst_verdict(results)
    overall_label = overall.value.upper()
    print(f"\n  FALSIFY CHECK — {overall_label}")
    print(f"  trades={n_trades}  params={n_params}  trials={n_trials}")

    if passthrough and any(passthrough.values()):
        parts = []
        if passthrough.get("symbol"):
            parts.append(f"symbol={passthrough['symbol']}")
        if passthrough.get("timeframe"):
            parts.append(f"timeframe={passthrough['timeframe']}")
        print(f"  {'  '.join(parts)}")

    if date_range:
        print(
            f"  date_range={date_range['first_entry']} → {date_range['last_exit']}"
        )

    print()

    for r in results:
        label = r.verdict.value.upper()
        print(f"  [{label:4s}] {r.name}")
        print(f"         {r.explanation}")
        print()

    if trials_was_default and overall != Verdict.pass_:
        print(
            "  NOTE: --trials was left at default (1). If you grid-searched "
            "strategy variants, the real overfitting risk is higher.\n"
        )


def _sha256_file(path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="falsify",
        description="Deterministic overfitting checks for backtest trade CSVs.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(
        "check",
        help="Run statistical checks against a trade CSV",
    )
    check.add_argument("csv_path", help="Path to a canonical trade CSV")
    check.add_argument(
        "--params",
        type=int,
        required=True,
        help="Number of free parameters the strategy was tuned on (no default — you must state it)",
    )
    check.add_argument(
        "--trials",
        type=int,
        default=1,
        help="Number of strategy variants tried before this one (default: 1)",
    )
    check.add_argument(
        "--from",
        dest="input_format",
        choices=["tradingview"],
        default=None,
        help="Input format adapter (e.g. 'tradingview'). Omit for canonical CSV.",
    )
    check.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of the human report",
    )

    args = parser.parse_args()

    if args.command != "check":
        parser.error(f"unknown command: {args.command}")

    # --trials has no sensible default — a silent default would hide real overfitting.
    # The report must say so when it's left at 1.
    trials_was_default = args.trials == 1

    try:
        if args.input_format is not None:
            adapter = ADAPTERS[args.input_format]
            trades, passthrough = adapter(args.csv_path)
        else:
            trades, passthrough = load_trades(args.csv_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    run_result = run_checks(trades, args.params, args.trials)

    # ── dataset block (date_range from actual data) ──
    date_range = {
        "first_entry": str(trades["entry_time"].min()),
        "last_exit": str(trades["exit_time"].max()),
    }

    if args.json:
        file_hash = _sha256_file(args.csv_path)
        output = {
            "schema_version": 1,
            "engine_version": __version__,
            "input": {
                "path": args.csv_path,
                "sha256": file_hash,
                "n_trades": len(trades),
            },
            "declared": {
                "params": args.params,
                "trials": args.trials,
                "trials_was_default": trials_was_default,
            },
            "dataset": {
                "symbol": passthrough["symbol"],
                "timeframe": passthrough["timeframe"],
                "date_range": date_range,
            },
            "verdict": worst_verdict(run_result.results).value,
            "checks": [_result_to_dict(r) for r in run_result.results],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(output, indent=2 if sys.stdout.isatty() else None))
    else:
        _print_human_report(
            run_result.results,
            len(trades),
            args.params,
            args.trials,
            trials_was_default,
            passthrough=passthrough,
            date_range=date_range,
        )

    raise SystemExit(0 if worst_verdict(run_result.results) == Verdict.pass_ else 1)


if __name__ == "__main__":
    main()
