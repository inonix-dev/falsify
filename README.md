# falsify

Deterministic checks for backtested trading strategies, run before you take
them live — like `npm audit` for overfitting.

```bash
falsify check trades.csv --params 8
```

No AI/LLM calls. No dashboard, no billing. Free forever.

## Install

```bash
pip install falsify-backtest
```

## Quick start

### TradingView (most common)

Export your strategy's "List of Trades" from TradingView, then:

```bash
falsify check ~/Downloads/BTCUSD_Strategy_Trades.csv --from tradingview --params 6
```

No manual CSV conversion needed. The adapter pairs Entry/Exit rows,
maps `Profit` → `pnl`, and extracts `symbol`/`timeframe` automatically.

### Canonical CSV

If you already have a 4-column CSV (`entry_time,exit_time,pnl,side`):

```bash
# A backtest that looks too good to be true (12 parameters, 42 trades)
falsify check examples/known_overfit.csv --params 12
# → FAIL — param_overfit_ratio below the 10:1 floor

# A backtest that holds up (2 parameters, 200 trades)
falsify check examples/known_good.csv --params 2
# → PASS on all three checks
```

## Checks

| Check | What it does | Fail threshold |
|---|---|---|
| `sample_size` | Binomial test — is the win rate distinguishable from 50/50? | n < 30 trades |
| `deflated_sharpe` | Deflates Sharpe ratio for multiple testing (Bailey & López de Prado, 2014) | DSR < 0.5 |
| `param_overfit_ratio` | Trades per free parameter — heuristic overfitting signal | ratio < 10 |

The overall verdict is the worst of the three checks.

## JSON output

```bash
falsify check trades.csv --params 8 --json
```

## Run record

`--json` outputs a structured run record — one JSON object per invocation.
Append results over time to build a history:

```bash
falsify check trades.csv --params 8 --json >> runs.jsonl
```

Migration from v1: v1's `--json` had no `schema_version` and a top-level
`n_trades`. v2 nests it under `input`. Records without `schema_version`
are v1 (flat shape) — readers should branch on its presence.

Schema (version 1):

| Field | Description |
|---|---|
| `schema_version` | Run record schema version (`1`) |
| `engine_version` | Engine version (`falsify --version`) |
| `input.path` | CSV path as provided |
| `input.sha256` | SHA-256 of the raw CSV file |
| `input.n_trades` | Number of trades |
| `declared.params` | Free parameters (user-provided) |
| `declared.trials` | Strategy variants tried (user-provided) |
| `declared.trials_was_default` | Whether `--trials` was left at default |
| `dataset.symbol` | Passthrough: symbol if present in CSV, else `null` |
| `dataset.timeframe` | Passthrough: timeframe if present in CSV, else `null` |
| `dataset.date_range` | `{first_entry, last_exit}` computed from trade timestamps |
| `verdict` | Overall: `pass`, `warn`, or `fail` |
| `checks[]` | Per-check results with name, verdict, value, threshold, explanation, and inputs |
| `created_at` | UTC timestamp (ISO-8601) |

Example:

```json
{
  "schema_version": 1,
  "engine_version": "0.1.0",
  "input": {
    "path": "examples/known_good.csv",
    "sha256": "a1b2c3...",
    "n_trades": 200
  },
  "declared": {
    "params": 2,
    "trials": 1,
    "trials_was_default": true
  },
  "dataset": {
    "symbol": null,
    "timeframe": null,
    "date_range": {
      "first_entry": "2024-01-01T09:00:00+00:00",
      "last_exit": "2024-06-28T16:00:00+00:00"
    }
  },
  "verdict": "pass",
  "checks": [
    {
      "name": "sample_size",
      "verdict": "pass",
      "value": 200,
      "threshold": 30,
      "explanation": "n=200 trades, win rate 62% statistically distinguishable from chance at p=0.00",
      "inputs": {"n_trades": 200, "n_wins": 124}
    }
  ],
  "created_at": "2026-09-10T12:00:00+00:00"
}
```

## False-negative corpus

`examples/corpus/` holds 10 backtests with known ground truth — 6 bad
strategies the engine must not pass, 3 good ones it must pass, and 1
documented blind spot (in-regime backtest v1 cannot see — needs held-out
data, out of engine scope). CI fails on any false negative or false
positive:

```bash
python -m pytest tests/test_corpus.py -s   # prints the scoreboard
python3 examples/corpus/generate.py         # regenerates the synthetic CSVs
```

Current score: 6/6 bad caught, 3/3 good pass, 1 tracked gap.

## Development

```bash
pip install -e .
pip install pytest
python -m pytest tests/
```

## License

MIT
