"""CSV loader + validator for the canonical trade CSV schema.

Schema (SPEC-engine-v1.md):
    entry_time,exit_time,pnl,side
    2026-01-03T09:00:00Z,2026-01-03T14:00:00Z,120.50,long

Extra columns are ignored. Malformed rows raise ValueError naming the row
number (1-indexed, header is row 1, first data row is row 2).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ("entry_time", "exit_time", "pnl", "side")
VALID_SIDES = frozenset({"long", "short"})

# Sentinel for ambiguous passthrough values (e.g. portfolio with multiple symbols).
# Distinguishes "column exists but has conflicting values" from "column absent" (None).
MULTIPLE_SENTINEL = "<multiple>"


def _canonical_digest(df: pd.DataFrame) -> str:
    """Compute a content-addressable SHA-256 of normalized trade data.

    Normalization rules (any deviation changes the hash — pin a test):
      1. Rows sorted by (entry_time, exit_time, pnl, side) ascending —
         all four, because entry_time alone is not unique: simultaneous
         entries (same bar, multi-symbol or scalping) would otherwise let
         raw file row order leak into the hash.
      2. Timestamps rendered via pandas isoformat (UTC, tz-aware).
      3. pnl rendered with ``:.10g`` (platform-invariant, no trailing zeros).
      4. side lowercased and stripped.
      5. One row per line, no trailing newline, UTF-8 encoding.

    The raw file hash (``input.sha256``) lives at ``input.sha256`` and is
    *not* replaced by this — they answer different questions: "which exact
    bytes did I receive" vs "which trades does this represent".
    """
    if len(df) == 0:
        return hashlib.sha256(b"").hexdigest()

    # 1. Total order over every field — makes the hash independent of CSV
    #    row order even when several trades open on the same timestamp.
    sorted_df = df.sort_values(
        ["entry_time", "exit_time", "pnl", "side"], kind="mergesort"
    ).reset_index(drop=True)

    lines: list[str] = []
    for _, row in sorted_df.iterrows():
        entry = pd.to_datetime(row["entry_time"], utc=True)
        exit_ = pd.to_datetime(row["exit_time"], utc=True)
        pnl = float(row["pnl"])
        side = str(row["side"]).strip().lower()
        lines.append(
            f"{entry.isoformat()},{exit_.isoformat()},{pnl:.10g},{side}"
        )

    canonical = "\n".join(lines)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def extract_passthrough(
    df: pd.DataFrame, symbol_col: str, timeframe_col: str
) -> dict[str, str | None]:
    """Pull an optional symbol/timeframe value out of a raw CSV DataFrame.

    Never computed, never validated — just echoed if every row agrees on one
    value. Returns:
      - the value as a string if all non-null rows agree,
      - ``MULTIPLE_SENTINEL`` (``"<multiple>"``) if the column exists but
        rows disagree — this distinguishes ambiguity from absence,
      - ``None`` if the column is absent entirely.
    """
    passthrough: dict[str, str | None] = {"symbol": None, "timeframe": None}
    for key, col in (("symbol", symbol_col), ("timeframe", timeframe_col)):
        if col in df.columns:
            val = df[col].dropna().unique()
            if len(val) == 1:
                passthrough[key] = str(val[0])
            elif len(val) > 1:
                passthrough[key] = MULTIPLE_SENTINEL
            # len == 0: all-null column stays None
    return passthrough


def load_trades(
    path: str | Path,
) -> tuple[pd.DataFrame, dict[str, str | None], str]:
    """Load and validate a trade CSV.

    Returns (df, passthrough, canonical_sha256):
      - df has columns [entry_time, exit_time, pnl, side] where
        entry_time/exit_time are datetime64[ns, UTC], pnl is float64,
        side is str;
      - passthrough is {"symbol": ... | None, "timeframe": ... | None}
        echoed from optional `symbol`/`timeframe` columns, if present
        and unambiguous;
      - canonical_sha256 is a SHA-256 hex digest of the normalized
        trade content (sorted by entry_time, consistent float format,
        lowercase side).

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
    canonical_hash = _canonical_digest(out)
    return out, passthrough, canonical_hash


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
