"""CSV loader + validator for the canonical trade CSV schema.

Schema (SPEC-engine-v1.md):
    entry_time,exit_time,pnl,side
    2026-01-03T09:00:00Z,2026-01-03T14:00:00Z,120.50,long

Extra columns are ignored. Malformed rows raise ValueError naming the row
number (1-indexed, header is row 1, first data row is row 2).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("entry_time", "exit_time", "pnl", "side")
VALID_SIDES = frozenset({"long", "short"})


def extract_passthrough(
    df: pd.DataFrame, symbol_col: str, timeframe_col: str
) -> dict[str, str | None]:
    """Pull an optional symbol/timeframe value out of a raw CSV DataFrame.

    Never computed, never validated — just echoed if every row agrees on one
    value. Ambiguous (multiple distinct values) or absent columns yield None.
    """
    passthrough: dict[str, str | None] = {"symbol": None, "timeframe": None}
    for key, col in (("symbol", symbol_col), ("timeframe", timeframe_col)):
        if col in df.columns:
            val = df[col].dropna().unique()
            passthrough[key] = str(val[0]) if len(val) == 1 else None
    return passthrough


def load_trades(path: str | Path) -> tuple[pd.DataFrame, dict[str, str | None]]:
    """Load and validate a trade CSV.

    Returns (df, passthrough): df has columns [entry_time, exit_time, pnl,
    side] where entry_time/exit_time are datetime64[ns, UTC], pnl is
    float64, side is str; passthrough is {"symbol": ... | None,
    "timeframe": ... | None} echoed from optional `symbol`/`timeframe`
    columns, if present and unambiguous.

    Raises:
        FileNotFoundError: path does not exist.
        ValueError: malformed header, empty dataset, or a data row fails
            validation — message names the offending row number.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise ValueError(f"row 1: cannot parse CSV header — {exc}") from exc

    _validate_header(df)
    if len(df) == 0:
        raise ValueError("empty dataset")

    passthrough = extract_passthrough(df, "symbol", "timeframe")

    out = pd.DataFrame()
    out["entry_time"] = df["entry_time"]
    out["exit_time"] = df["exit_time"]
    out["pnl"] = df["pnl"]
    out["side"] = df["side"]

    for i, row in out.iterrows():
        row_no = i + 2  # 0-indexed + skip header
        _validate_pnl(row["pnl"], row_no)
        _validate_side(row["side"], row_no)

    out["entry_time"] = _parse_datetime(out["entry_time"], "entry_time")
    out["exit_time"] = _parse_datetime(out["exit_time"], "exit_time")

    for i, (entry, exit_) in enumerate(
        zip(out["entry_time"], out["exit_time"])
    ):
        row_no = i + 2
        if exit_ <= entry:
            raise ValueError(
                f"row {row_no}: exit_time ({exit_}) must be after "
                f"entry_time ({entry})"
            )

    out["pnl"] = out["pnl"].astype("float64")
    return out, passthrough


def _validate_header(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"row 1: missing required column(s): {', '.join(missing)}"
        )


def _validate_pnl(value, row_no: int) -> None:
    if pd.isna(value):
        raise ValueError(f"row {row_no}: pnl is missing")
    try:
        float(value)
    except (TypeError, ValueError):
        raise ValueError(f"row {row_no}: non-numeric pnl '{value}'") from None


def _validate_side(value, row_no: int) -> None:
    if pd.isna(value) or str(value).strip().lower() not in VALID_SIDES:
        raise ValueError(
            f"row {row_no}: side must be 'long' or 'short', got '{value}'"
        )


def _parse_datetime(series: pd.Series, col: str) -> pd.Series:
    parsed = pd.to_datetime(series, utc=True, errors="coerce")
    bad = parsed.isna() & series.notna()
    if bad.any():
        idx = bad.idxmax()
        row_no = int(idx) + 2
        raise ValueError(
            f"row {row_no}: invalid {col} '{series.iloc[idx]}'"
        )
    return parsed
