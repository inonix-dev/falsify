"""Unit tests for falsify.io — CSV loader + validator."""

from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import pytest

from falsify.io import load_trades


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
        df = load_trades(tmp_csv)
        assert len(df) == 2
        assert list(df.columns) == ["entry_time", "exit_time", "pnl", "side"]
        assert df["pnl"].dtype == "float64"

    def test_extra_columns_ignored(self, tmp_csv: Path):
        _write_csv(tmp_csv, [
            ["entry_time", "exit_time", "pnl", "side", "symbol", "notes"],
            ["2026-01-03T09:00:00Z", "2026-01-03T14:00:00Z", "120.50", "long", "BTCUSDT", "test"],
        ])
        df = load_trades(tmp_csv)
        assert len(df) == 1
        assert list(df.columns) == ["entry_time", "exit_time", "pnl", "side"]

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
