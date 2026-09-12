"""Byte-level determinism of the run record.

The whole cloud layer is built on "same input → same record": a ledger that
can't tell a re-run from a new result can't count trials. If this test goes
red, that layer is unsafe to build on — CI must fail, not warn.

`created_at` is the one field allowed to move (cloud needs it to order runs),
so it is stripped from the raw bytes before comparison rather than parsed
around — everything else is compared as bytes.
"""

from __future__ import annotations

import re
import subprocess
import sys

import pytest

CREATED_AT = re.compile(r', ?"created_at": ?"[^"]*"')


def _record(csv_path: str, params: int) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "falsify.cli", "check", csv_path,
         "--params", str(params), "--json"],
        capture_output=True,
        text=True,
    )
    assert proc.stdout, f"no JSON on stdout: {proc.stderr}"
    return CREATED_AT.sub("", proc.stdout)


@pytest.mark.parametrize(
    "csv_path,params",
    [
        ("examples/known_good.csv", 2),
        ("examples/known_overfit.csv", 12),
    ],
)
def test_record_is_byte_identical_across_runs(csv_path, params):
    first = _record(csv_path, params)
    second = _record(csv_path, params)
    assert first == second


def test_created_at_is_actually_present():
    # Guards the stripper above: if created_at were renamed or dropped, the
    # regex would silently match nothing and the test would still pass.
    proc = subprocess.run(
        [sys.executable, "-m", "falsify.cli", "check",
         "examples/known_good.csv", "--params", "2", "--json"],
        capture_output=True,
        text=True,
    )
    assert CREATED_AT.search(proc.stdout), "no created_at field to strip"
