# SPEC-engine-v1.md — CSV schema + verdict output for the v1 stat-ensemble

> **Used by:** [PLAN-engine-v1.md](../plan/PLAN-engine-v1.md)

---

## Shape (data / API / schema)

### Input — canonical trade CSV

One row per closed trade. Header required, exact column names:

| column | type | required | notes |
|---|---|---|---|
| `entry_time` | ISO8601 string | yes | |
| `exit_time` | ISO8601 string | yes | must be > `entry_time` |
| `pnl` | float | yes | net P&L, sign matters (loss = negative) |
| `side` | `long` \| `short` | yes | |

No other columns are read in v1 (extra columns are ignored, not an error — lets
users hand over a raw platform export without pre-cleaning it column-by-column).

Example:
```csv
entry_time,exit_time,pnl,side
2026-01-03T09:00:00Z,2026-01-03T14:00:00Z,120.50,long
2026-01-04T02:00:00Z,2026-01-04T05:30:00Z,-40.00,short
```

### CLI

```bash
falsify check trades.csv --params 8 [--trials 1] [--json]
```

- `--params N` — **required**, no default. Count of free parameters the
  strategy was tuned on (lookback length, threshold, MA period, …). Forcing
  the user to state it is deliberate — a silent default would let a
  12-parameter strategy quietly report as if it had 1.
- `--trials N` — optional, default `1`. Number of strategy variants tried
  before this one shipped (grid-search size, number of backtests run). Feeds
  the Deflated Sharpe Ratio's multiple-testing correction. Defaulting to 1
  understates real overfitting risk for anyone who grid-searched — the
  `deflated_sharpe` check's `warn`/`fail` output must say so explicitly
  whenever `--trials` is left at the default.
- `--json` — machine-readable output (schema below) instead of the human report.

### Output — JSON shape (`--json`)

```json
{
  "n_trades": 42,
  "verdict": "warn",
  "checks": [
    {
      "name": "sample_size",
      "verdict": "pass",
      "value": 42,
      "threshold": 30,
      "explanation": "n=42 trades, win rate 57% not distinguishable from chance at p=0.31"
    },
    {
      "name": "deflated_sharpe",
      "verdict": "warn",
      "value": 0.71,
      "threshold": 0.95,
      "explanation": "Probabilistic Sharpe 0.71 after deflating for 1 trial (--trials not set — likely overstated)"
    },
    {
      "name": "param_overfit_ratio",
      "verdict": "fail",
      "value": 5.25,
      "threshold": 10,
      "explanation": "5.25 trades per parameter (8 params, 42 trades) — below the 10:1 floor"
    }
  ]
}
```

`verdict` (top-level) = worst of the three (`fail` > `warn` > `pass`).

## Checks (formulas, cite the source)

1. **`sample_size`** — two-sided binomial test, H0: win rate = 0.5.
   `fail` if `n_trades < 30` (hard floor, regardless of p-value — a p<0.05
   result on n=14 is still not trustworthy). Otherwise `warn` if p > 0.05,
   `pass` if p ≤ 0.05.
2. **`deflated_sharpe`** — Probabilistic Sharpe Ratio deflated by `--trials`
   (Bailey & López de Prado, "The Deflated Sharpe Ratio", 2014). `fail` if
   DSR < 0.5, `warn` if 0.5–0.95, `pass` if ≥ 0.95.
3. **`param_overfit_ratio`** — `n_trades / params`. `fail` if < 10, `warn` if
   10–30, `pass` if ≥ 30. Heuristic, not a proven law — documented as such in
   `--help` output, not presented as a hard statistical result like the other two.

## Edge cases

| input | expected behavior |
|---|---|
| `n_trades < 5` | `sample_size` = `fail` immediately; `deflated_sharpe` reports `"insufficient_data"` instead of a number — never silently compute a Sharpe on 3 trades |
| `--params` omitted | CLI exits with usage error, does not run — no silent default |
| non-numeric `pnl` cell | validator error naming the row number, no partial report |
| `entry_time` ≥ `exit_time` on a row | validator error naming the row number |
| header present, zero data rows | error `"empty dataset"`, not a false `pass` |
| extra/unknown columns present | ignored silently — not an error |

## Examples

```bash
falsify check examples/known_overfit.csv --params 12   # expect: fail (param_overfit_ratio)
falsify check examples/known_good.csv --params 2        # expect: pass on all three
```
