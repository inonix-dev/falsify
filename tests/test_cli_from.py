"""CLI integration tests for --from flag, dataset passthrough, and v2.6 features."""

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


# ── v2.6: --strategy passthrough ──


class TestStrategyPassthrough:
    """--strategy is a pure passthrough — engine ignores it."""

    def test_strategy_in_json_output(self):
        tv = str(FIXTURES / "tradingview_raw.csv")
        code, out, _ = _run_cli(
            "check", tv, "--from", "tradingview", "--params", "2",
            "--strategy", "ema-cross", "--json",
        )
        rec = json.loads(out)
        assert rec["dataset"]["strategy"] == "ema-cross"

    def test_strategy_none_when_omitted(self):
        tv = str(FIXTURES / "tradingview_raw.csv")
        code, out, _ = _run_cli(
            "check", tv, "--from", "tradingview", "--params", "2", "--json",
        )
        rec = json.loads(out)
        assert rec["dataset"]["strategy"] is None

    def test_strategy_in_human_output(self):
        tv = str(FIXTURES / "tradingview_raw.csv")
        code, out, _ = _run_cli(
            "check", tv, "--from", "tradingview", "--params", "2",
            "--strategy", "ema-cross",
        )
        assert "strategy=ema-cross" in out


# ── v2.6: canonical_sha256 in JSON ──


class TestCanonicalSha256InJson:
    """input.canonical_sha256 must be present and differ from input.sha256."""

    def test_canonical_sha256_present(self):
        csv = str(FIXTURES / "tradingview_canonical.csv")
        code, out, _ = _run_cli("check", csv, "--params", "2", "--json")
        rec = json.loads(out)
        assert "canonical_sha256" in rec["input"]
        assert len(rec["input"]["canonical_sha256"]) == 64  # SHA-256 hex

    def test_canonical_sha256_differs_from_file_sha256(self):
        """File hash and canonical hash answer different questions."""
        csv = str(FIXTURES / "tradingview_canonical.csv")
        code, out, _ = _run_cli("check", csv, "--params", "2", "--json")
        rec = json.loads(out)
        assert rec["input"]["sha256"] != rec["input"]["canonical_sha256"]

    def test_canonical_sha256_deterministic(self):
        """Same CSV → same canonical_sha256 across runs."""
        csv = str(FIXTURES / "tradingview_canonical.csv")
        _, out1, _ = _run_cli("check", csv, "--params", "2", "--json")
        _, out2, _ = _run_cli("check", csv, "--params", "2", "--json")
        r1 = json.loads(out1)
        r2 = json.loads(out2)
        assert r1["input"]["canonical_sha256"] == r2["input"]["canonical_sha256"]

    def test_canonical_sha256_present_in_adapter_path(self):
        """canonical_sha256 must also appear when using --from."""
        tv = str(FIXTURES / "tradingview_raw.csv")
        code, out, _ = _run_cli(
            "check", tv, "--from", "tradingview", "--params", "2", "--json",
        )
        rec = json.loads(out)
        assert "canonical_sha256" in rec["input"]
        assert len(rec["input"]["canonical_sha256"]) == 64
