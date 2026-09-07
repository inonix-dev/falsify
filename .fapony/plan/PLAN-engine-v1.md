# PLAN-engine-v1.md — falsify engine v1 (CSV-in, deterministic stat-ensemble CLI)

> **Status:** 🚧 in-progress · **Owner:** delamind · **Created:** 2026-09-06
> **Source spec:** [SPEC-engine-v1.md](../spec/SPEC-engine-v1.md)

---

## 1. Goal (why)

Give a trader an offline, deterministic way to check whether their own backtest
(any platform's trade-list export) is statistically real or a false positive
— small-sample overconfidence, un-deflated Sharpe, over-parameterized fitting
— before they risk real money on it. This is the free, public, MIT-licensed
core: no login, no network call, no vendor lock to any platform.

## 2. Scope (do / don't do)

**Do:**
- CLI (`falsify check <csv> --params N`) that loads a canonical trade CSV and
  runs 3 deterministic checks: sample-size significance, deflated Sharpe
  ratio, parameter-overfit ratio
- Human-readable report by default, `--json` for machine-readable output
- Ship as an installable Python package (pip), MIT license
- 2 example CSVs (one seeded to fail, one seeded to pass) used as the
  self-check

**Don't do:**
- No AI/LLM calls — non-deterministic and costs money, out of scope for the
  free deterministic core (phase 2, lives in the private `cloud` repo)
- No connectors (TradingView, Binance, Canalis, freqtrade) — CSV-in only;
  connectors are a paid-tier concern, different repo
- No dashboard/web UI — stdout/JSON only
- No decile-monotonicity / signal-strength check — needs a data shape (signal
  rank per trade) not defined yet, don't invent it mid-chunk
- No lookahead-bias detection — that requires parsing strategy source code
  (Pine/Python), a different tool shape than a CSV-in stat check; separate
  effort entirely

## 3. Done criteria (how we know it's finished)

- `pip install -e .` succeeds from a clean checkout
- `falsify check examples/known_overfit.csv --params 12` exits with overall
  `verdict: fail` and names `param_overfit_ratio` as the failing check
- `falsify check examples/known_good.csv --params 2` exits with overall
  `verdict: pass`
- Each of the 3 checks has a unit test against a synthetic dataset with a
  known expected verdict (not just "runs without crashing")
- `falsify check --json` output validates against the schema in
  [SPEC-engine-v1.md](../spec/SPEC-engine-v1.md)
- Omitting `--params` exits non-zero with a usage error, never a silent default

## 4. Constraints / Hard rules (must not violate)

- Zero network calls anywhere in the engine — must run fully offline (this is
  the trust claim: no data ever leaves the trader's machine)
- Every threshold/formula in the output must trace to the formula documented
  in the spec — no unexplained magic number
- No silent defaults on inputs that change the verdict's honesty (`--params`
  has no default; `--trials` defaults to 1 but the report must say so
  out loud when it's left at default)
- Stdlib + numpy/scipy/pandas only for v1 — no heavy ML dependency
- A malformed CSV must fail loudly with the offending row number, never
  produce a wrong-but-confident report

## 5. Risks & Escape hatches (if it fails)

| risk | likelihood | impact | escape hatch |
|---|---|---|---|
| Deflated Sharpe formula implemented subtly wrong | medium | high — this is the one thing the whole "independent referee" positioning rests on | cross-check the implementation against a worked example from Bailey & López de Prado's paper with a known expected output; cite the source in the spec and in a code comment next to the formula |
| Thresholds (n<30, 10:1 param ratio) read as arbitrary to a rigorous reviewer | medium | medium | document each threshold's rationale in the spec (done); keep them CLI-overridable flags, not hardcoded constants |
| Scope creep mid-chunk into decile-monotonicity / connectors / AI-gate | high (natural to want "just one more check") | medium — blows a single-session chunk | Section 2 explicitly excludes them; if opencode is tempted, it stops and flags rather than expanding scope |
| CSV format disagrees across source platforms (TradingView vs freqtrade export shapes differ) | high | medium | v1 defines exactly one canonical schema (spec); per-platform adapters are an explicit phase-2 concern, not solved here |

## 6. Steps (what in which order)

1. **Scaffold the package** — `pyproject.toml`, `LICENSE` (MIT), minimal
   `README.md` stub, `src/falsify/` package layout. Deliverable:
   `pip install -e .` succeeds and `falsify --help` runs.
2. **CSV loader + validator** — `falsify.io.load_trades(path)` per the schema
   in the spec, raising the documented errors on malformed input. Deliverable:
   unit tests for every edge case row in the spec's edge-case table.
3. **`sample_size` check** — binomial significance test. Deliverable: function
   + unit test with a synthetic dataset at a known p-value.
4. **`deflated_sharpe` check** — Probabilistic/Deflated Sharpe Ratio.
   Deliverable: function + unit test cross-checked against a worked example
   from the source paper (see Risks).
5. **`param_overfit_ratio` check** — trades-per-parameter heuristic.
   Deliverable: function + unit test.
6. **CLI wiring** — `falsify check <csv> --params N [--trials N] [--json]`
   aggregating the 3 checks into one report (human + JSON per spec).
   Deliverable: runs end-to-end on both example CSVs.
7. **Example datasets + quick-start** — `examples/known_overfit.csv`,
   `examples/known_good.csv`, and a "Quick start" section in `README.md`
   showing both verdicts. Deliverable: matches Done Criteria exactly.

## 7. Examples (make it concrete)

```bash
falsify check examples/known_overfit.csv --params 12   # → verdict: fail
falsify check examples/known_good.csv --params 2        # → verdict: pass
```

Full CSV schema, JSON output shape, and edge-case table: see
[SPEC-engine-v1.md](../spec/SPEC-engine-v1.md).

## 8. References

- [SPEC-engine-v1.md](../spec/SPEC-engine-v1.md) — schema, formulas, edge cases
- Bailey, D. & López de Prado, M. (2014), "The Deflated Sharpe Ratio" —
  source for the `deflated_sharpe` check
- Positioning note (not a spec, just context for future chunks): this engine
  is the free, public, MIT half of an open-core split — the paid half
  (dashboard, connectors, AI-gate/debate, billing) lives in the private
  `falsify-cloud` worktree and is planned separately once this chunk ships.
