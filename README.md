# falsify

Deterministic checks for backtested trading strategies, run before you take
them live — like `npm audit` for overfitting.

```bash
falsify check trades.csv --params 8
```

Checks (see [.fapony/spec/engine-v1.md](.fapony/spec/engine-v1.md)):
sample size, deflated Sharpe ratio, param/trade overfit ratio.

No AI/LLM calls. No dashboard, no billing. Free forever.

## Install

```bash
pip install -e .
```

## Status

v1 in progress — CLI scaffolded, checks not implemented yet.
