"""Unit tests for falsify.checks."""

from __future__ import annotations

import numpy as np
import pytest

from falsify.checks import (
    CheckResult,
    Verdict,
    deflated_sharpe,
    param_overfit_ratio,
    sample_size,
    worst_verdict,
)


class TestSampleSize:
    """Two-sided binomial test, H0: win rate = 0.5."""

    def test_n_below_5_is_fail(self):
        r = sample_size(4, 2)
        assert r.verdict == Verdict.fail
        assert "insufficient data" in r.explanation.lower()

    def test_n_below_30_is_fail(self):
        r = sample_size(14, 8)
        assert r.verdict == Verdict.fail
        assert "hard floor" in r.explanation.lower()

    def test_n_30_high_winrate_pass(self):
        # 22/30 wins = 73% → p < 0.05
        r = sample_size(30, 22)
        assert r.verdict == Verdict.pass_

    def test_n_30_balanced_warn(self):
        # 15/30 wins = 50% → p = 1.0
        r = sample_size(30, 15)
        assert r.verdict == Verdict.warn

    def test_n_60_moderate_warn(self):
        # 35/60 wins ≈ 58% → p > 0.05 (not significant)
        r = sample_size(60, 35)
        assert r.verdict == Verdict.warn

    def test_value_is_n_trades(self):
        r = sample_size(50, 25)
        assert r.value == 50

    def test_threshold_is_30(self):
        r = sample_size(50, 25)
        assert r.threshold == 30


class TestDeflatedSharpe:
    """Probabilistic Sharpe Ratio deflated for multiple testing.

    Source: Bailey & López de Prado, "The Deflated Sharpe Ratio", 2014.
    """

    def test_n_below_5_is_insufficient(self):
        r = deflated_sharpe(2.0, 4, 1, 0.0, 3.0)
        assert r.verdict == Verdict.fail
        assert "insufficient_data" == r.value

    def test_high_sharpe_single_trial_pass(self):
        # SR=2.0, n=100, 1 trial → DSR should be very high
        r = deflated_sharpe(2.0, 100, 1, 0.0, 3.0)
        assert r.verdict == Verdict.pass_
        assert r.value >= 0.95

    def test_very_low_sharpe_fail(self):
        # SR=0.05, n=30, 1 trial → PSR ~0.63, still warn not fail
        # Need very low SR with many trials to push below 0.5
        r = deflated_sharpe(0.05, 30, 1000, 0.0, 3.0)
        assert r.verdict == Verdict.fail

    def test_deflation_reduces_sharpe(self):
        # With many trials, DSR should be lower than PSR
        # SR=0.5, n=60 → PSR ~0.97, with 100 trials DSR should drop
        r1 = deflated_sharpe(0.5, 60, 1, 0.0, 3.0)
        r2 = deflated_sharpe(0.5, 60, 100, 0.0, 3.0)
        assert r2.value < r1.value

    def test_zero_sharpe_warns(self):
        # SR=0 → PSR=0.5 (exactly at the warn/fail boundary)
        # The formula gives 0.5, which maps to warn (>= 0.5)
        r = deflated_sharpe(0.0, 100, 1, 0.0, 3.0)
        assert r.verdict == Verdict.warn
        assert r.value == pytest.approx(0.5, abs=0.01)

    def test_warn_range(self):
        # SR=0.5, n=100, 1 trial → DSR should be in warn range (0.5-0.95)
        r = deflated_sharpe(0.5, 100, 1, 0.0, 3.0)
        assert r.verdict in (Verdict.warn, Verdict.pass_)

    def test_threshold_is_0_95(self):
        r = deflated_sharpe(1.0, 100, 1, 0.0, 3.0)
        assert r.threshold == 0.95

    def test_explanation_mentions_trials(self):
        r = deflated_sharpe(1.0, 100, 10, 0.0, 3.0)
        assert "10 trials" in r.explanation


class TestParamOverfitRatio:
    """Trades-per-parameter heuristic."""

    def test_fail_below_10(self):
        r = param_overfit_ratio(42, 12)
        assert r.verdict == Verdict.fail
        assert r.value == pytest.approx(3.5, abs=0.01)

    def test_warn_10_to_30(self):
        r = param_overfit_ratio(200, 10)
        assert r.verdict == Verdict.warn
        assert r.value == pytest.approx(20.0, abs=0.01)

    def test_pass_above_30(self):
        r = param_overfit_ratio(200, 2)
        assert r.verdict == Verdict.pass_
        assert r.value == pytest.approx(100.0, abs=0.01)

    def test_threshold_is_10(self):
        r = param_overfit_ratio(100, 5)
        assert r.threshold == 10

    def test_explanation_includes_ratio(self):
        r = param_overfit_ratio(50, 5)
        assert "10.00" in r.explanation


class TestWorstVerdict:
    def test_worst_of_three(self):
        results = [
            CheckResult("a", Verdict.pass_, 1, 1, "ok"),
            CheckResult("b", Verdict.warn, 1, 1, "ok"),
            CheckResult("c", Verdict.fail, 1, 1, "ok"),
        ]
        assert worst_verdict(results) == Verdict.fail

    def test_all_pass(self):
        results = [
            CheckResult("a", Verdict.pass_, 1, 1, "ok"),
            CheckResult("b", Verdict.pass_, 1, 1, "ok"),
        ]
        assert worst_verdict(results) == Verdict.pass_
