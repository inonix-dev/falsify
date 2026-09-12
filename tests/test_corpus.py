"""False-negative corpus — the test that lets us claim the engine is trustworthy.

Each case in examples/corpus/manifest.json has a KNOWN ground truth:
  - gate=must_not_pass → a bad strategy; overall PASS is a false negative (fail CI)
  - gate=must_pass     → a good strategy; anything but PASS is a false positive (fail CI)
  - gate=documented_gap → known v1 blind spot (xfail: expected to pass-while-bad)

Detection rate today: 6/7 bad caught (85.7%), 1 documented gap (regime-fit
needs held-out data — cloud scope, engine non-goal per roadmap).

To regenerate the synthetic CSVs: python3 examples/corpus/generate.py
(must stay byte-identical; the test pins row counts as a tripwire).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from falsify.checks import worst_verdict
from falsify.cli import run_checks
from falsify.io import load_trades

CORPUS_DIR = Path(__file__).resolve().parent.parent / "examples" / "corpus"
MANIFEST = json.loads((CORPUS_DIR / "manifest.json").read_text())
CASES = MANIFEST["cases"]
CASE_IDS = [c["file"] for c in CASES]

# Row-count tripwire: regenerate via generate.py → these must not drift.
EXPECTED_ROWS = {
    "bad_small_sample_lucky.csv": 14,
    "../known_overfit.csv": 42,
    "bad_random_walk.csv": 200,
    "bad_hidden_trials.csv": 80,
    "bad_martingale_fat_tail.csv": 100,
    "bad_single_outlier.csv": 60,
    "bad_cherry_picked_regime.csv": 150,
    "../known_good.csv": 200,
    "good_moderate_edge.csv": 120,
    "good_minimal_clean.csv": 100,
}


def _run(case: dict) -> str:
    path = (CORPUS_DIR / case["file"]).resolve()
    trades = load_trades(path)
    assert len(trades) == EXPECTED_ROWS[case["file"]], (
        f"{case['file']}: {len(trades)} rows, expected "
        f"{EXPECTED_ROWS[case['file']]} — regenerate via generate.py?"
    )
    run_result = run_checks(trades, case["params"], case["trials"])
    return worst_verdict(run_result.results).value


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_corpus_gate(case: dict):
    """FN gate: bad must not pass, good must pass."""
    if case["gate"] == "documented_gap":
        actual = _run(case)
        assert actual == "pass", (
            f"{case['file']}: blind spot got CAUGHT ({actual}) — "
            "good news, update manifest.json gate to must_not_pass"
        )
        pytest.xfail(f"known v1 blind spot: {case['rationale']}")
    actual = _run(case)
    if case["gate"] == "must_not_pass":
        assert actual != "pass", (
            f"FALSE NEGATIVE: {case['file']} is a known-bad strategy "
            f"but the engine PASSED it (params={case['params']}, "
            f"trials={case['trials']})"
        )
        assert actual == case["expected"], (
            f"{case['file']}: expected {case['expected']}, got {actual} — "
            "update manifest.json if the engine honestly changed"
        )
    elif case["gate"] == "must_pass":
        assert actual == "pass", (
            f"FALSE POSITIVE: {case['file']} is a known-good strategy "
            f"but the engine returned {actual}"
        )
    else:  # pragma: no cover
        raise AssertionError(f"unknown gate: {case['gate']}")


def test_detection_rate_report():
    """Human-readable scoreboard (run with -s to see it)."""
    caught = total_bad = good_ok = total_good = 0
    lines = []
    for case in CASES:
        if case["gate"] == "documented_gap":
            lines.append(f"  [GAP ] {case['file']} — bad but passes (tracked blind spot)")
            continue
        actual = _run(case)
        if case["label"] == "bad":
            total_bad += 1
            caught += actual != "pass"
            lines.append(f"  [{'CAUGHT' if actual != 'pass' else 'FN!!!'}] {case['file']} → {actual}")
        else:
            total_good += 1
            good_ok += actual == "pass"
            lines.append(f"  [{'OK' if actual == 'pass' else 'FP!!!'}] {case['file']} → {actual}")
    print(
        f"\n  FALSE-NEGATIVE CORPUS: {caught}/{total_bad} bad caught, "
        f"{good_ok}/{total_good} good pass\n" + "\n".join(lines)
    )
    assert caught == total_bad, f"{total_bad - caught} false negative(s) in corpus"
    assert good_ok == total_good, f"{total_good - good_ok} false positive(s) in corpus"


def test_hidden_trials_dishonesty_delta():
    """Same CSV, honest vs default --trials: proves why the CLI nags.

    bad_hidden_trials.csv with --trials 1 PASSES (the FN a grid-searcher
    gets for free by omitting the flag); with --trials 200 it FAILS.
    Non-gating documentation of the dishonesty gap — the engine can only
    deflate trials it is told about.
    """
    case = next(c for c in CASES if c["file"] == "bad_hidden_trials.csv")
    path = (CORPUS_DIR / case["file"]).resolve()
    trades = load_trades(path)
    default = worst_verdict(run_checks(trades, case["params"], 1).results).value
    honest = worst_verdict(run_checks(trades, case["params"], 200).results).value
    assert (default, honest) == ("pass", "fail"), (
        f"trial-delta broke: --trials 1 → {default}, --trials 200 → {honest} "
        "(expected pass/fail — update manifest + this test if intended)"
    )


def test_determinism():
    """Same input → identical JSON (except created_at).

    The cloud layer depends on this property: two runs of the same file
    must produce byte-identical records so results can be deduplicated.
    """
    import subprocess
    import sys

    csv = str((CORPUS_DIR / "../known_good.csv").resolve())
    cmd = [sys.executable, "-m", "falsify.cli", "check", csv, "--params", "2", "--json"]

    obj1 = json.loads(subprocess.check_output(cmd))
    obj2 = json.loads(subprocess.check_output(cmd))

    obj1.pop("created_at")
    obj2.pop("created_at")

    assert obj1 == obj2, "Non-deterministic JSON output"


def test_small_input_record_is_strict_json(tmp_path):
    """Degenerate inputs (n=2) must still emit strict JSON.

    pandas skew/kurtosis are NaN for tiny samples; the record must carry
    null instead — bare NaN is rejected by RFC 8259 parsers (jq, cloud).
    """
    import subprocess
    import sys

    csv = tmp_path / "tiny.csv"
    csv.write_text(
        "entry_time,exit_time,pnl,side\n"
        "2026-01-03T09:00:00Z,2026-01-03T14:00:00Z,100.0,long\n"
        "2026-01-04T09:00:00Z,2026-01-04T14:00:00Z,-50.0,short\n"
    )
    cmd = [sys.executable, "-m", "falsify.cli", "check", str(csv), "--params", "1", "--json"]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    assert proc.returncode == 1  # fail verdict — record is still emitted

    def _strict(const):
        raise ValueError(f"non-strict JSON constant: {const}")

    record = json.loads(proc.stdout.decode(), parse_constant=_strict)
    assert record["verdict"] == "fail"
    dsr_inputs = next(c["inputs"] for c in record["checks"] if c["name"] == "deflated_sharpe")
    assert dsr_inputs["skew"] is None and dsr_inputs["kurtosis"] is None
