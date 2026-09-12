"""Deterministic format adapters for non-canonical trade CSVs.

Each adapter converts a vendor-specific export into the canonical 4-column
schema (entry_time, exit_time, pnl, side). Adapters are pure functions:
no I/O beyond reading the file, no network, no AI.

Adding a new adapter:
  1. User must provide a real export file + fixture
  2. Adapter must be deterministic (no randomness, no heuristics)
  3. Orphan rows (unpaired Entry/Exit) must raise ValueError with row numbers
  4. Passthrough columns (symbol, timeframe) are echoed, never computed
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from falsify.io import extract_passthrough


def from_tradingview(
    path: str | Path,
) -> tuple[pd.DataFrame, dict[str, str | None]]:
    """Convert a TradingView 'List of Trades' export to canonical shape.

    TradingView pairs trades as 2 rows each:
      - Entry long / Exit long  (or Entry short / Exit short)
      - Same "Trade #" for both rows
      - "Profit" only on Exit row

    Returns:
        (df, passthrough) where df has columns [entry_time, exit_time, pnl, side]
        and passthrough is {"symbol": ... | None, "timeframe": ... | None}.

    Raises:
        ValueError: orphan rows, mismatched pairs, missing columns, or
            empty dataset.  Message always names the offending CSV row number.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    try:
        raw = pd.read_csv(path)
    except Exception as exc:
        raise ValueError(
            f"row 1: cannot parse TradingView CSV header — {exc}"
        ) from exc

    _validate_tv_header(raw)
    if len(raw) == 0:
        raise ValueError("empty dataset")

    passthrough = extract_passthrough(raw, "Symbol", "Interval")

    # ── pair rows by Trade # ──
    trades: list[dict] = []
    for trade_no, group in raw.groupby("Trade #", sort=True):
        if len(group) != 2:
            raise ValueError(
                f"trade #{trade_no}: expected 2 rows (Entry + Exit), "
                f"got {len(group)}"
            )

        types = group["Type"].str.strip().str.lower().tolist()
        if types[0] not in ("entry long", "entry short"):
            raise ValueError(
                f"row {_csv_row(group.index[0])}: expected Entry, "
                f"got '{group['Type'].iloc[0]}'"
            )
        if types[1] not in ("exit long", "exit short"):
            raise ValueError(
                f"row {_csv_row(group.index[1])}: expected Exit, "
                f"got '{group['Type'].iloc[1]}'"
            )

        entry_side = types[0].replace("entry ", "")
        exit_side = types[1].replace("exit ", "")
        if entry_side != exit_side:
            raise ValueError(
                f"trade #{trade_no}: Entry is '{entry_side}' but Exit "
                f"is '{exit_side}' — must match"
            )

        entry_row = group.iloc[0]
        exit_row = group.iloc[1]
        entry_row_no = _csv_row(group.index[0])
        exit_row_no = _csv_row(group.index[1])

        # Same validation the canonical path gets in io.py: reject garbage
        # timestamps and inverted pairs loudly instead of persisting them
        # into date_range of a content-hashed run record.
        entry_ts = _parse_tv_datetime(
            entry_row["Date/Time"], entry_row_no, "entry"
        )
        exit_ts = _parse_tv_datetime(
            exit_row["Date/Time"], exit_row_no, "exit"
        )
        if exit_ts <= entry_ts:
            raise ValueError(
                f"row {exit_row_no}: exit_time ({exit_ts}) must be after "
                f"entry_time ({entry_ts})"
            )

        profit_raw = exit_row["Profit"]
        if pd.isna(profit_raw):
            raise ValueError(
                f"row {_csv_row(group.index[1])}: Profit is missing"
            )
        try:
            pnl = float(profit_raw)
        except (TypeError, ValueError):
            raise ValueError(
                f"row {_csv_row(group.index[1])}: non-numeric "
                f"Profit '{profit_raw}'"
            ) from None

        trades.append(
            {
                "entry_time": entry_ts,
                "exit_time": exit_ts,
                "pnl": pnl,
                "side": entry_side,
            }
        )

    if not trades:
        raise ValueError("empty dataset")

    return pd.DataFrame(trades), passthrough


def _validate_tv_header(df: pd.DataFrame) -> None:
    """Check that required TradingView columns are present."""
    required = {"Trade #", "Type", "Date/Time", "Profit"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"row 1: missing required TradingView column(s): "
            f"{', '.join(sorted(missing))}"
        )


def _parse_tv_datetime(value, row_no: int, which: str) -> pd.Timestamp:
    """Parse a TradingView Date/Time cell, mirroring io._parse_datetime.

    Raises:
        ValueError: unparseable timestamp — message names the CSV row number.
    """
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"row {row_no}: invalid {which}_time '{value}'")
    return parsed


def _csv_row(pandas_index: int) -> int:
    """Convert pandas DataFrame index to 1-indexed CSV row number (header = row 1)."""
    return int(pandas_index) + 2


ADAPTERS = {
    "tradingview": from_tradingview,
}
