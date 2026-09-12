"""CLI integration tests for --from flag and dataset passthrough."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _run_cli(*args: str) -> tuple[int, str, str]:
    """Run falsify CLI via subprocess and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "-m", "falsify.cli"] + list(args)
    proc = subprocess.run(cmd, capture_output=True, check=False)
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()


class TestFromTradingView:
    """End-to-end: TV raw → --from tradingview → verdict."""

    def test_human_output_has_verdict(self):
        """10 trades with 2 params → FAIL (expected: n<30), but command succeeds."""
        tv = str(FIXTURES / "tradingview_raw.csv")
        code, out, _ = _run_cli("check", tv, "--from", "tradingview", "--params", "2")
        assert code == 1  # FAIL verdict
        assert "FALSIFY CHECK" in out
        assert "trades=10" in out
        assert "FAIL" in out

    def test_json_has_dataset_block(self):
        tv = str(FIXTURES / "tradingview_raw.csv")
        code, out, _ = _run_cli(
            "check", tv, "--from", "tradingview", "--params", "2", "--json"
        )
        assert code == 1  # FAIL verdict
        rec = json.loads(out)
        assert "dataset" in rec
        assert rec["dataset"]["symbol"] is None
        assert rec["dataset"]["timeframe"] is None
        assert "date_range" in rec["dataset"]
        assert rec["dataset"]["date_range"]["first_entry"] is not None
        assert rec["dataset"]["date_range"]["last_exit"] is not None

    def test_json_has_passthrough_symbol(self):
        tv = str(FIXTURES / "tradingview_with_symbol.csv")
        code, out, _ = _run_cli(
            "check", tv, "--from", "tradingview", "--params", "2", "--json"
        )
        rec = json.loads(out)
        assert rec["dataset"]["symbol"] == "BTCUSD"
        assert rec["dataset"]["timeframe"] == "60"

    def test_human_output_shows_symbol(self):
        tv = str(FIXTURES / "tradingview_with_symbol.csv")
        code, out, _ = _run_cli("check", tv, "--from", "tradingview", "--params", "2")
        assert "symbol=BTCUSD" in out
        assert "timeframe=60" in out

    def test_backward_compat_no_from(self):
        """Canonical CSV without --from still works."""
        canon = str(FIXTURES / "tradingview_canonical.csv")
        code, out, _ = _run_cli("check", canon, "--params", "2")
        assert code == 1  # FAIL verdict (10 trades, 2 params)
        assert "trades=10" in out

    def test_json_has_date_range(self):
        """dataset.date_range present even without passthrough columns."""
        canon = str(FIXTURES / "tradingview_canonical.csv")
        code, out, _ = _run_cli("check", canon, "--params", "2", "--json")
        rec = json.loads(out)
        assert rec["dataset"]["date_range"]["first_entry"] is not None
        assert rec["dataset"]["date_range"]["last_exit"] is not None

    def test_orphan_row_error_from_cli(self):
        tv = str(FIXTURES / "tradingview_orphan.csv")
        _, out, err = _run_cli("check", tv, "--from", "tradingview", "--params", "2")
        combined = out + err
        assert "trade #2" in combined.lower() or "row" in combined.lower()
