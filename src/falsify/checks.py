"""Three deterministic statistical checks for backtest overfitting.

Checks:
    1. sample_size       — two-sided binomial test (H0: win rate = 0.5)
    2. deflated_sharpe   — Probabilistic Sharpe Ratio deflated by trials
                          (Bailey & López de Prado, "The Deflated Sharpe Ratio", 2014)
    3. param_overfit_ratio — n_trades / params heuristic
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy import stats


class Verdict(Enum):
    pass_ = "pass"
    warn = "warn"
    fail = "fail"


@dataclass
class CheckResult:
    name: str
    verdict: Verdict
    value: float | str
    threshold: float
    explanation: str


def sample_size(n_trades: int, n_wins: int) -> CheckResult:
    """Two-sided binomial test, H0: win rate = 0.5.

    Rules (from spec):
        - fail if n_trades < 30 (hard floor)
        - warn if p > 0.05
        - pass if p <= 0.05
    """
    if n_trades < 5:
        return CheckResult(
            name="sample_size",
            verdict=Verdict.fail,
            value=n_trades,
            threshold=30,
            explanation=f"n={n_trades} trades — insufficient data for any statistical test",
        )

    if n_trades < 30:
        return CheckResult(
            name="sample_size",
            verdict=Verdict.fail,
            value=n_trades,
            threshold=30,
            explanation=f"n={n_trades} trades — below the 30-trade hard floor",
        )

    win_rate = n_wins / n_trades
    # Two-sided binomial test: H0: p = 0.5
    # stats.binomtest replaces deprecated stats.binom_test (scipy >= 1.14)
    result = stats.binomtest(n_wins, n_trades, 0.5, alternative="two-sided")
    p_value = result.pvalue

    if p_value <= 0.05:
        v = Verdict.pass_
    else:
        v = Verdict.warn

    return CheckResult(
        name="sample_size",
        verdict=v,
        value=n_trades,
        threshold=30,
        explanation=(
            f"n={n_trades} trades, win rate {win_rate:.0%} "
            f"{'not distinguishable from chance' if p_value > 0.05 else 'statistically distinguishable from chance'} "
            f"at p={p_value:.2f}"
        ),
    )


def deflated_sharpe(
    sharpe_observed: float,
    n_trades: int,
    n_trials: int,
    skew: float,
    kurtosis: float,
) -> CheckResult:
    """Probabilistic Sharpe Ratio deflated for multiple testing.

    Source: Bailey & López de Prado, "The Deflated Sharpe Ratio", 2014.
    Formula: DSR = Phi( (PSR_obs - 1) / sqrt(Var(PSR_obs)) )
    where PSR_obs = norm.cdf( (SR_obs - SR_benchmark) * sqrt(n-1) / sqrt(1 - skew*SR_obs + (kurt-1)/4 * SR_obs^2) )

    For SR_benchmark = 0 (our case: testing against "no skill"):
        PSR = norm.cdf( SR_obs * sqrt(n-1) / sqrt(1 - skew*SR_obs + (kurt-1)/4 * SR_obs^2) )

    Rules (from spec):
        - fail if DSR < 0.5
        - warn if 0.5 <= DSR < 0.95
        - pass if DSR >= 0.95
    """
    if n_trades < 5:
        return CheckResult(
            name="deflated_sharpe",
            verdict=Verdict.fail,
            value="insufficient_data",
            threshold=0.95,
            explanation=f"n={n_trades} trades — insufficient data to compute a meaningful Sharpe ratio",
        )

    n = n_trades
    sr = sharpe_observed

    # PSR: Probabilistic Sharpe Ratio (SR benchmark = 0)
    # PSR = Phi( (SR_obs * sqrt(n-1)) / sqrt(1 - skew*SR_obs + (kurt-1)/4 * SR_obs^2) )
    denom_var = 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr**2
    if denom_var <= 0:
        # Edge case: variance estimate non-positive → treat as degenerate
        psr = 1.0 if sr > 0 else 0.0
    else:
        psr = stats.norm.cdf(sr * np.sqrt(n - 1) / np.sqrt(denom_var))

    # Deflation: adjust PSR for multiple testing (Bailey & López de Prado, 2014)
    # E[max(SR)] over n_trials iid normal draws with std = sqrt(Var(PSR))
    # Approximation: E[max_SR] ≈ sqrt(2 * ln(n_trials)) * sqrt(denom_var / (n-1))
    #   (for n_trials > 1; when n_trials == 1, no deflation)
    if n_trials > 1 and denom_var > 0:
        expected_max_sr = np.sqrt(2.0 * np.log(n_trials)) * np.sqrt(denom_var / (n - 1))
        # Recompute PSR against the deflated benchmark
        dsr = stats.norm.cdf(
            (sr - expected_max_sr) * np.sqrt(n - 1) / np.sqrt(denom_var)
        )
    else:
        dsr = psr

    if dsr >= 0.95:
        v = Verdict.pass_
    elif dsr >= 0.5:
        v = Verdict.warn
    else:
        v = Verdict.fail

    explanation = f"Probabilistic Sharpe {psr:.2f}"
    if n_trials > 1:
        explanation += f" → deflated to {dsr:.2f} after {n_trials} trials"
    else:
        explanation += " (1 trial — no deflation applied)"
    explanation += f" — SR={sr:.2f}, n={n}"

    return CheckResult(
        name="deflated_sharpe",
        verdict=v,
        value=round(dsr, 4),
        threshold=0.95,
        explanation=explanation,
    )


def param_overfit_ratio(n_trades: int, n_params: int) -> CheckResult:
    """Trades-per-parameter heuristic.

    Rules (from spec):
        - fail if ratio < 10
        - warn if 10 <= ratio < 30
        - pass if ratio >= 30
    """
    ratio = n_trades / n_params

    if ratio >= 30:
        v = Verdict.pass_
    elif ratio >= 10:
        v = Verdict.warn
    else:
        v = Verdict.fail

    return CheckResult(
        name="param_overfit_ratio",
        verdict=v,
        value=round(ratio, 2),
        threshold=10,
        explanation=f"{ratio:.2f} trades per parameter ({n_params} params, {n_trades} trades)"
        + (" — below the 10:1 floor" if ratio < 10 else ""),
    )


def worst_verdict(results: list[CheckResult]) -> Verdict:
    """Return the worst verdict across all checks."""
    verdict_order = {Verdict.fail: 0, Verdict.warn: 1, Verdict.pass_: 2}
    return min(results, key=lambda r: verdict_order[r.verdict]).verdict
