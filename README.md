# falsify

Deterministic checks for backtested trading strategies, run before you take
them live — like `npm audit` for overfitting.

```bash
falsify check trades.csv --params 8
```

No AI/LLM calls. No dashboard, no billing. Free forever.

## Install

```bash
pip install -e .
```

## Quick start

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

## Development

```bash
pip install -e .
pip install pytest
python -m pytest tests/
```

## License

MIT
