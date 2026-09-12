# Contributing

falsify is a deterministic engine: CSV in → record out. That constraint drives
everything below.

## Engine invariants

Changes that violate these will be closed, no matter how good the code is:

- **No AI/LLM calls, no network, no state or config files.** The engine must
  produce the same record from the same CSV, on any machine, forever.
- **The engine has no stake in the result.** It never tunes, generates, or
  suggests strategies.
- **No new checks without a real user and a real case.** Open an issue with a
  CSV that the current checks get wrong, first.
- **The human report format is frozen.** People read it today. Add to `--json`
  instead.
- **Fail safe toward "don't know."** A check that can't decide should say so,
  not guess confidently.

## What's most useful

1. **False negatives** — a bad backtest falsify passes. This is the highest-value
   bug report in the project. Use the "False negative" issue template.
2. **False positives** — a sound backtest falsify fails.
3. **Import adapters** — a new `--from` source (broker/platform export).
4. Docs, typos, clearer explanations.

## Dev setup

```bash
pip install -e .
pip install pytest
python -m pytest tests/
```

## Pull requests

- One concern per PR. Small diffs get merged; large ones get questions.
- Tests are required for behavior changes. `tests/test_determinism.py` and
  `tests/test_corpus.py` must stay green — the corpus scoreboard is the
  project's actual contract.
- A new check or adapter needs a corpus case in `examples/corpus/` with
  documented ground truth.
- Conventional commit subjects (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Target `main`.

## Scope

Out of scope by design: dashboards, accounts, billing, hosted anything,
strategy generation, live trading. If a feature needs a server, it belongs in
a different project.
