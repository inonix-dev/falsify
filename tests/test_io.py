"""Unit tests for falsify.io — CSV loader + validator."""

from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import pytest

from falsify.io import MULTIPLE_SENTINEL, load_trades


@pytest.fixture
def tmp_csv(tmp_path: Path) -> Path:
    return tmp_path / "trades.csv"


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


class TestLoadTrades:
    def test_valid_csv(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long"],
            ["2026-01-04T02:00:00Z", "2026-01-04T05:30:00Z", "-40.00", "short"],
        ])
        df, _, _ = load_trades(tmp_csv)
        assert len(df) == 2
        assert list(df.columns) == ["entry_time", "exit_time", "pnl", "side"]
        assert df["pnl"].dtype == "float64"

    def test_extra_columns_ignored(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side", "symbol", "notes"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long", "BTCUSDT", "test"],
        ])
        df, _, _ = load_trades(tmp_csv)
        assert len(df) == 1
        assert list(df.columns) == ["entry_time", "exit_time", "pnl", "side"]

    def test_symbol_and_timeframe_passthrough(self, tmp_csv: Path):
        """Canonical CSV with symbol/timeframe columns echoes them, uncomputed."""
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side", "symbol", "timeframe"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long", "BTCUSDT", "60"],
        ])
        _, passthrough, _ = load_trades(tmp_csv)
        assert passthrough == {"symbol": "BTCUSDT", "timeframe": "60"}

    def test_no_symbol_column_is_null(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long"],
        ])
        _, passthrough, _ = load_trades(tmp_csv)
        assert passthrough == {"symbol": None, "timeframe": None}

    def test_missing_column_raises(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50"],
        ])
        with pytest.raises(ValueError, match="missing required column"):
            load_trades(tmp_csv)

    def test_empty_dataset_raises(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
        ])
        with pytest.raises(ValueError, match="empty dataset"):
            load_trades(tmp_csv)

    def test_non_numeric_pnl_raises(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "abc", "long"],
        ])
        with pytest.raises(ValueError, match="row 2.*non-numeric pnl"):
            load_trades(tmp_csv)

    def test_invalid_side_raises(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "both"],
        ])
        with pytest.raises(ValueError, match="row 2.*side must be"):
            load_trades(tmp_csv)

    def test_entry_ge_exit_raises(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T14:00:00Z", "2026-01-03T09:00:00Z", "120.50", "long"],
        ])
        with pytest.raises(ValueError, match="row 2.*exit_time.*must be after"):
            load_trades(tmp_csv)

    def test_entry_eq_exit_raises(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T09:00:00Z", "120.50", "long"],
        ])
        with pytest.raises(ValueError, match="exit_time.*must be after"):
            load_trades(tmp_csv)

    def test_invalid_datetime_raises(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["not-a-date", "2026-01-03T14:00:00Z", "120.50", "long"],
        ])
        with pytest.raises(ValueError, match="row 2.*invalid entry_time"):
            load_trades(tmp_csv)

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_trades(tmp_path / "nonexistent.csv")

    def test_nan_pnl_raises(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "", "long"],
        ])
        with pytest.raises(ValueError, match="row 2.*pnl is missing"):
            load_trades(tmp_csv)


# ── v2.6: canonical_sha256 ──

# Pin test: if normalization rules change, this literal must change too.
PINNED_KNOWN_GOOD_HASH = "552af7e9b7ae20154f8dd70c34aa049c8fd51830d2e3785659f1e814900ca651"


class TestCanonicalDigest:
    """Content-addressable hash of normalized trade data."""

    def test_known_good_pin(self):
        """Pin the canonical hash of examples/known_good.csv.

        If this breaks after a normalization change, update the literal above.
        """
        _, _, canonical = load_trades("examples/known_good.csv")
        assert canonical == PINNED_KNOWN_GOOD_HASH

    def test_different_row_order_same_hash(self, tmp_csv: Path):
        """Same trades, different CSV row order → same canonical hash."""
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            # Reversed order
            ["2026-01-04T02:00:00Z", "2026-01-04T05:30:00Z", "-40.00", "short"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long"],
        ])
        _, _, hash_reversed = load_trades(tmp_csv)

        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long"],
            ["2026-01-04T02:00:00Z", "2026-01-04T05:30:00Z", "-40.00", "short"],
        ])
        _, _, hash_forward = load_trades(tmp_csv)

        assert hash_reversed == hash_forward

    def test_different_trades_different_hash(self, tmp_csv: Path):
        """Different trade data → different canonical hash (no hash collision)."""
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long"],
        ])
        _, _, hash_a = load_trades(tmp_csv)

        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "999.99", "long"],
        ])
        _, _, hash_b = load_trades(tmp_csv)

        assert hash_a != hash_b

    def test_float_repr_invariance(self, tmp_csv: Path):
        """120.50 vs 120.5000 → same canonical hash (float repr doesn't matter)."""
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long"],
        ])
        _, _, hash_a = load_trades(tmp_csv)

        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.5000", "long"],
        ])
        _, _, hash_b = load_trades(tmp_csv)

        assert hash_a == hash_b

    def test_side_normalization_in_hash(self, tmp_csv: Path):
        """Side is lowercased in canonical form — 'Long' and 'long' hash the same."""
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "Long"],
        ])
        _, _, hash_upper = load_trades(tmp_csv)

        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long"],
        ])
        _, _, hash_lower = load_trades(tmp_csv)

        assert hash_upper == hash_lower


# ── v2.6: <multiple> sentinel ──


class TestMultipleSentinel:
    """Ambiguous passthrough values use '<multiple>' sentinel."""

    def test_ambiguous_symbol_yields_sentinel(self, tmp_csv: Path):
        """Column exists with conflicting values → '<multiple>'."""
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side", "symbol"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long", "BTC"],
            ["2026-01-04T02:00:00Z", "2026-01-04T05:30:00Z", "-40.00", "short", "ETH"],
        ])
        _, passthrough, _ = load_trades(tmp_csv)
        assert passthrough["symbol"] == MULTIPLE_SENTINEL

    def test_absent_column_yields_none(self, tmp_csv: Path):
        """Column absent → None (different from '<multiple>')."""
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long"],
        ])
        _, passthrough, _ = load_trades(tmp_csv)
        assert passthrough["symbol"] is None

    def test_single_value_yields_value(self, tmp_csv: Path):
        """Column exists with one unique value → that value."""
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side", "symbol"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long", "BTC"],
            ["2026-01-04T02:00:00Z", "2026-01-04T05:30:00Z", "-40.00", "short", "BTC"],
        ])
        _, passthrough, _ = load_trades(tmp_csv)
        assert passthrough["symbol"] == "BTC"


def test_canonical_hash_stable_when_entry_times_tie():
    """Simultaneous entries must not let file row order leak into the hash.

    entry_time alone is not a unique key — a multi-symbol or scalping
    backtest opens several trades on the same bar. Sorting on entry_time
    only is stable, so the raw row order survived into the digest and a
    re-export with a different order looked like a new trial to the ledger.
    """
    import csv
    import tempfile
    from pathlib import Path

    rows = [
        {"entry_time": "2024-01-01T09:00:00Z", "exit_time": "2024-01-01T10:00:00Z",
         "pnl": "1", "side": "long"},
        {"entry_time": "2024-01-01T09:00:00Z", "exit_time": "2024-01-01T11:00:00Z",
         "pnl": "2", "side": "short"},
    ] * 20

    def digest(ordered):
        tmp = Path(tempfile.mkdtemp()) / "t.csv"
        with tmp.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(ordered[0]))
            w.writeheader()
            w.writerows(ordered)
        return load_trades(tmp)[2]

    assert digest(rows) == digest(rows[::-1])
