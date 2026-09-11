"""False-negative corpus generator — deterministic, seeded, byte-identical output.

Each case is a backtest with a KNOWN ground truth (bad strategy that must NOT
pass, or good strategy that must pass). Run:

    python3 examples/corpus/generate.py

Regenerates the 8 synthetic CSVs in this directory. The 2 trust-anchor files
(bad_overfit_ratio, good_strong_edge) live in examples/ and are referenced
from manifest.json, not duplicated here.

Design rule: every synthetic case uses a FRESH numpy Generator with its own
seed (no shared streams), so each file is reproducible in isolation. Fixed
arrays (martingale, outlier, small-sample) use no RNG at all.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

CORPUS_DIR = Path(__file__).resolve().parent
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _write(name: str, pnls: np.ndarray, durations_h: list[int] | None = None) -> None:
    """Write canonical trade CSV: entry<exit, side matches pnl sign."""
    path = CORPUS_DIR / name
    t = START
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entry_time", "exit_time", "pnl", "side"])
        for i, pnl in enumerate(float(x) for x in pnls):
            dur = (durations_h[i % len(durations_h)] if durations_h else 3)  # hours
            entry, exit_ = t, t + timedelta(hours=dur)
            w.writerow([
                entry.isoformat(),
                exit_.isoformat(),
                f"{pnl:.2f}",
                "long" if pnl > 0 else "short",
            ])
            t = exit_ + timedelta(hours=1)
    print(f"wrote {path.name} ({len(pnls)} trades)")


def main() -> None:
    # b1 — lucky small sample: 79% win rate, but n=14 < 30 floor → must FAIL
    _write("bad_small_sample_lucky.csv", np.array([120.0] * 11 + [-80.0] * 3))

    # b3 — pure noise: N(0,100), 200 trades → must FAIL (via deflated_sharpe)
    _write("bad_random_walk.csv", np.random.default_rng(7).normal(0, 100, 200))

    # b4 — decent in-sample SR that evaporates under honest trial count.
    # trials=1 → PASS (the FN you get when the user omits --trials);
    # trials=200 → FAIL. Manifest gates on trials=200.
    _write("bad_hidden_trials.csv", np.random.default_rng(1).normal(35, 100, 80))

    # b5 — martingale trap: 85% win rate PASSES sample_size, but the left
    # tail kills Sharpe → must FAIL (via deflated_sharpe). Win-rate-only
    # thinking would ship this; the engine must not.
    _write(
        "bad_martingale_fat_tail.csv",
        np.array([50.0] * 85 + [-500.0] * 15),
    )

    # b6 — lottery ticket: 1 outlier pays for 59 losers. Win rate 2% is
    # "significant" (two-sided test) so sample_size passes; DSR only warns.
    # Must NOT pass overall → gate is must_not_pass (warn counts as caught).
    _write("bad_single_outlier.csv", np.array([-20.0] * 59 + [3000.0]))

    # b7 — DOCUMENTED GAP: in-regime backtest with a real-but-fragile edge.
    # v1 has no held-out info in the CSV, so the engine PASSES a strategy
    # that dies out-of-sample. Kept to measure the blind spot honestly —
    # manifest marks known_limitation:true, the gate expects the FN.
    _write(
        "bad_cherry_picked_regime.csv",
        np.random.default_rng(33).normal(90, 110, 150),
    )

    # g2 — moderate real edge, 60% wins → must PASS
    rng = np.random.default_rng(5)
    _write(
        "good_moderate_edge.csv",
        np.concatenate([rng.normal(150, 80, 72), rng.normal(-100, 60, 48)]),
    )

    # g3 — minimal clean edge, 65% wins → must PASS
    rng = np.random.default_rng(21)
    _write(
        "good_minimal_clean.csv",
        np.concatenate([rng.normal(140, 70, 65), rng.normal(-95, 55, 35)]),
    )


if __name__ == "__main__":
    main()
