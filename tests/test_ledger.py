"""Chunk 1 — P0 ledger: log + status (declared vs observed).

Covers the plan §3 done criteria:
- same file checked 3 times → observed = 1
- 3 distinct trade sets, one strategy → observed = 3
- same file re-exported (bytes differ, canonical hash same) → observed unchanged
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from falsify_agent import ledger

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("FALSIFY_HOME", str(tmp_path / ".falsify"))
    return tmp_path / ".falsify"


def make_record(strategy="ema-cross", sha="canon-1", trials=1,
                verdict="pass", created_at="2026-09-01T00:00:00+00:00"):
    return {
        "schema_version": 1,
        "engine_version": "0.1.0",
        "input": {"path": "x.csv", "sha256": f"raw-{sha}",
                  "canonical_sha256": sha, "n_trades": 200},
        "declared": {"params": 2, "trials": trials,
                     "trials_was_default": trials == 1},
        "dataset": {"symbol": None, "timeframe": None, "strategy": strategy,
                    "date_range": {"first_entry": "2026-01-01", "last_exit": "2026-02-01"}},
        "verdict": verdict,
        "checks": [],
        "created_at": created_at,
    }


def log_json(record) -> None:
    ledger.append_record(record)


def test_same_file_three_times_observed_one(home):
    rec = make_record()
    for _ in range(3):
        log_json(rec)
    assert ledger.status("ema-cross")["runs"] == 3
    assert ledger.observed_trials("ema-cross") == 1


def test_three_distinct_sets_observed_three(home):
    for i in range(3):
        log_json(make_record(sha=f"canon-{i}"))
    assert ledger.observed_trials("ema-cross") == 3


def test_reexport_bytes_differ_canonical_same(home):
    # CRLF / column-order re-export: raw sha256 + path differ, canonical same.
    log_json(make_record(sha="canon-1"))
    rec = make_record(sha="canon-1")
    rec["input"]["sha256"] = "raw-other"
    rec["input"]["path"] = "x-crlf.csv"
    log_json(rec)
    assert ledger.observed_trials("ema-cross") == 1


def test_no_strategy_logged_but_not_counted(home, capsys):
    rec = make_record(strategy=None)
    log_json(rec)
    assert ledger.status("ema-cross") is None
    assert ledger.observed_trials("ema-cross") == 0


def test_strategy_names_are_case_sensitive(home):
    log_json(make_record(strategy="Ema-Cross"))
    assert ledger.status("ema-cross") is None
    assert ledger.observed_trials("Ema-Cross") == 1


def test_corrupt_line_skipped_with_warning(home, capsys):
    log_json(make_record())
    with open(home / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write("{broken\n")
        f.write(json.dumps({"schema_version": 999}) + "\n")
    assert ledger.observed_trials("ema-cross") == 1
    err = capsys.readouterr().err
    assert "runs.jsonl:2" in err
    assert "runs.jsonl:3" in err


def test_malformed_but_valid_json_skipped_not_crash(home, capsys):
    log_json(make_record())
    rec = make_record()
    rec["input"] = "oops"          # schema_version ok, shape wrong
    rec["declared"] = []
    log_json(rec)
    assert ledger.observed_trials("ema-cross") == 1  # only the well-formed run
    assert ledger.status("ema-cross")["runs"] == 2
    assert ledger.status("ema-cross")["last_declared_trials"] is None


def test_status_json_shape(home):
    log_json(make_record(sha="a", verdict="fail", trials=1,
                         created_at="2026-09-01T00:00:00+00:00"))
    log_json(make_record(sha="b", verdict="pass", trials=1,
                         created_at="2026-09-23T00:00:00+00:00"))
    s = ledger.status("ema-cross")
    assert s == {
        "strategy": "ema-cross",
        "runs": 2,
        "observed_trials": 2,
        "last_declared_trials": 1,
        "last_trials_was_default": True,
        "first_at": "2026-09-01T00:00:00+00:00",
        "last_at": "2026-09-23T00:00:00+00:00",
        "verdicts": {"pass": 1, "fail": 1, "warn": 0},
    }


def run_agent(*args, input_text=None, env_home=None):
    import os
    env = dict(os.environ)
    if env_home is not None:
        env["FALSIFY_HOME"] = str(env_home)
    return subprocess.run(
        [sys.executable, "-m", "falsify_agent.cli", *args],
        input=input_text, capture_output=True, text=True, env=env, cwd=REPO,
    )


def test_cli_log_then_status_end_to_end(home):
    engine = subprocess.run(
        [sys.executable, "-m", "falsify.cli", "check",
         "examples/known_good.csv", "--params", "2",
         "--strategy", "ema-cross", "--json"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert engine.returncode == 0
    r = run_agent("log", input_text=engine.stdout, env_home=home)
    assert r.returncode == 0, r.stderr
    assert "ledger นับได้ 1" in r.stdout
    r = run_agent("status", "ema-cross", env_home=home)
    assert r.returncode == 0
    assert "กรอก --trials 1 · ledger นับได้ 1" in r.stdout
    r = run_agent("status", "ema-cross", "--json", env_home=home)
    assert r.returncode == 0
    assert json.loads(r.stdout)["observed_trials"] == 1


def test_cli_status_unknown_strategy(home):
    r = run_agent("status", "nope", env_home=home)
    assert r.returncode == 1
    assert 'ยังไม่มี run ของ "nope"' in r.stderr
