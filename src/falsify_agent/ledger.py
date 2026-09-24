"""P0 ledger — append-only log of engine records + observed-trial counting.

Reads records produced by ``falsify check ... --json`` (schema_version 1).
Never imports the engine: the only contract is the public JSON record.

File: ``$FALSIFY_HOME/runs.jsonl`` (default ``~/.falsify``), one compact-JSON
engine record per line, verbatim (no wrapper, no extra fields).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCHEMA_VERSION = 1
VERDICTS = ("pass", "fail", "warn")


def home() -> Path:
    return Path(os.environ.get("FALSIFY_HOME", str(Path.home() / ".falsify")))


def ledger_path() -> Path:
    return home() / "runs.jsonl"


def append_record(record: dict) -> Path:
    """Append one engine record as a single compact-JSON line. Creates home dir."""
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return path


def _warn(lineno: int, reason: str) -> None:
    print(f"runs.jsonl:{lineno} {reason} — ข้าม", file=sys.stderr)


def iter_records(path: Path | None = None):
    """Yield ``(lineno, record)`` for every readable record.

    Corrupt lines and non-``1`` schema_versions are skipped with a stderr
    warning — never crash, never guess.
    """
    path = ledger_path() if path is None else path
    try:
        fp = open(path, encoding="utf-8")
    except FileNotFoundError:
        return
    with fp:
        for lineno, line in enumerate(fp, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                _warn(lineno, "อ่านไม่ได้")
                continue
            if not isinstance(record, dict) or record.get("schema_version") != SCHEMA_VERSION:
                _warn(lineno, f"schema_version != {SCHEMA_VERSION}")
                continue
            yield lineno, record


def _strategy_of(record: dict) -> str | None:
    dataset = record.get("dataset")
    if not isinstance(dataset, dict):
        return None
    strategy = dataset.get("strategy")
    return strategy if isinstance(strategy, str) and strategy else None


def strategy_runs(strategy: str, path: Path | None = None) -> list[dict]:
    """All ledger records for one strategy, in append order (exact name match)."""
    return [r for _, r in iter_records(path) if _strategy_of(r) == strategy]


def observed_trials(strategy: str, path: Path | None = None) -> int:
    """Distinct ``input.canonical_sha256`` values under one strategy name."""
    seen: set[str] = set()
    for record in strategy_runs(strategy, path):
        inputs = record.get("input")
        sha = inputs.get("canonical_sha256") if isinstance(inputs, dict) else None
        if isinstance(sha, str) and sha:
            seen.add(sha)
    return len(seen)


def status(strategy: str, path: Path | None = None) -> dict | None:
    """Summary dict for ``status --json``. None when the strategy has no runs."""
    runs = strategy_runs(strategy, path)
    if not runs:
        return None
    verdicts = {v: 0 for v in VERDICTS}
    for record in runs:
        verdict = record.get("verdict")
        if verdict in verdicts:
            verdicts[verdict] += 1
    last = runs[-1]
    declared = last.get("declared")
    if not isinstance(declared, dict):
        declared = {}
    return {
        "strategy": strategy,
        "runs": len(runs),
        "observed_trials": observed_trials(strategy, path),
        "last_declared_trials": declared.get("trials"),
        "last_trials_was_default": declared.get("trials_was_default"),
        "first_at": runs[0].get("created_at"),
        "last_at": last.get("created_at"),
        "verdicts": verdicts,
    }
