"""Tests for TradingView adapter — round-trip, orphans, passthrough."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from falsify.adapters import from_tradingview

FIXTURES = Path(__file__).parent / "fixtures"


# ── round-trip ──


class TestRoundTrip:
    """TV raw fixture → adapter → canonical must match hand-converted fixture."""

    def test_adapter_matches_canonical(self):
        tv_path = FIXTURES / "tradingview_raw.csv"
        canon_path = FIXTURES / "tradingview_canonical.csv"

        df, passthrough = from_tradingview(tv_path)
        expected = pd.read_csv(canon_path)

        assert list(df.columns) == ["entry_time", "exit_time", "pnl", "side"]
        assert len(df) == len(expected)

        # compare values (timestamps as strings for equality)
        for col in df.columns:
            actual_vals = df[col].tolist()
            expected_vals = expected[col].tolist()
            assert actual_vals == expected_vals, (
                f"column '{col}' mismatch:\n  actual:   {actual_vals}\n  expected: {expected_vals}"
            )

    def test_passthrough_none_when_columns_absent(self):
        tv_path = FIXTURES / "tradingview_raw.csv"
        _, passthrough = from_tradingview(tv_path)
        assert passthrough == {"symbol": None, "timeframe": None}

    def test_trade_count(self):
        tv_path = FIXTURES / "tradingview_raw.csv"
        df, _ = from_tradingview(tv_path)
        assert len(df) == 10


# ── passthrough ──


class TestPassthrough:
    """When Symbol/Interval columns exist, adapter extracts them."""

    def test_symbol_and_timeframe_extracted(self):
        tv_path = FIXTURES / "tradingview_with_symbol.csv"
        df, passthrough = from_tradingview(tv_path)
        assert passthrough["symbol"] == "BTCUSD"
        assert passthrough["timeframe"] == "60"
        assert len(df) == 2

    def test_canonical_cols_only(self):
        tv_path = FIXTURES / "tradingview_with_symbol.csv"
        df, _ = from_tradingview(tv_path)
        assert list(df.columns) == ["entry_time", "exit_time", "pnl", "side"]


# ── orphan rows ──


class TestOrphanRows:
    """Unpaired Entry/Exit must raise ValueError with row numbers."""

    def test_orphan_entry_raises(self):
        tv_path = FIXTURES / "tradingview_orphan.csv"
        with pytest.raises(ValueError, match="trade #2"):
            from_tradingview(tv_path)

    def test_error_message_includes_row(self):
        tv_path = FIXTURES / "tradingview_orphan.csv"
        with pytest.raises(ValueError) as exc_info:
            from_tradingview(tv_path)
        msg = str(exc_info.value)
        # must contain a row number
        assert "row" in msg.lower()


# ── error cases ──


class TestErrors:
    """Adapter must fail loudly on bad input."""

    def test_empty_dataset(self, tmp_path: Path):
        csv = tmp_path / "empty.csv"
        csv.write_text("Trade #,Type,Signal,Date/Time,Price,Contracts,Profit\n")
        with pytest.raises(ValueError, match="empty dataset"):
            from_tradingview(csv)

    def test_missing_column(self, tmp_path: Path):
        csv = tmp_path / "bad_header.csv"
        csv.write_text("Trade #,Type,Date/Time\n1,Entry long,2024-01-01\n")
        with pytest.raises(ValueError, match="missing required"):
            from_tradingview(csv)

    def test_non_numeric_profit(self, tmp_path: Path):
        csv = tmp_path / "bad_profit.csv"
        csv.write_text(
            '"Trade #","Type","Date/Time","Profit"\n'
            '1,"Entry long","2024-01-15 09:30:00",""\n'
            '1,"Exit long","2024-01-15 14:45:00","not_a_number"\n'
        )
        with pytest.raises(ValueError, match="non-numeric Profit"):
            from_tradingview(csv)

    def test_missing_profit(self, tmp_path: Path):
        csv = tmp_path / "nan_profit.csv"
        csv.write_text(
            '"Trade #","Type","Date/Time","Profit"\n'
            '1,"Entry long","2024-01-15 09:30:00",""\n'
            '1,"Exit long","2024-01-15 14:45:00",""\n'
        )
        with pytest.raises(ValueError, match="Profit is missing"):
            from_tradingview(csv)

    def test_mismatched_sides(self, tmp_path: Path):
        csv = tmp_path / "mismatch.csv"
        csv.write_text(
            '"Trade #","Type","Date/Time","Profit"\n'
            '1,"Entry long","2024-01-15 09:30:00",""\n'
            '1,"Exit short","2024-01-15 14:45:00","100"\n'
        )
        with pytest.raises(ValueError, match="must match"):
            from_tradingview(csv)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            from_tradingview("/nonexistent/file.csv")

    def test_invalid_datetime_raises_with_row(self, tmp_path: Path):
        """Garbage Date/Time must fail loudly (canonical path parity)."""
        csv = tmp_path / "bad_dt.csv"
        csv.write_text(
            '"Trade #","Type","Date/Time","Profit"\n'
            '1,"Entry long","not-a-date",""\n'
            '1,"Exit long","also-not-a-date","300.25"\n'
        )
        with pytest.raises(ValueError, match="row 2: invalid entry_time"):
            from_tradingview(csv)

    def test_exit_before_entry_raises(self, tmp_path: Path):
        """Inverted pair must fail loudly (canonical path parity)."""
        csv = tmp_path / "inverted.csv"
        csv.write_text(
            '"Trade #","Type","Date/Time","Profit"\n'
            '1,"Entry long","2024-01-15 14:45:00",""\n'
            '1,"Exit long","2024-01-15 09:30:00","300.25"\n'
        )
        with pytest.raises(ValueError, match="must be after"):
            from_tradingview(csv)
