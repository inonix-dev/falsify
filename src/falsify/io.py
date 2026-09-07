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


def load_trades(path: str | Path) -> pd.DataFrame:
    """Load and validate a trade CSV.

    Returns a DataFrame with columns [entry_time, exit_time, pnl, side]
    where entry_time/exit_time are datetime64[ns, UTC], pnl is float64,
    and side is str.

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
    return out


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
