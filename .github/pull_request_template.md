## What and why

<!-- One paragraph. Link the issue if there is one. -->

## Engine invariants

- [ ] No AI/LLM call, no network, no state or config file
- [ ] Same CSV still produces the same record (`tests/test_determinism.py` green)
- [ ] Human report format unchanged (JSON-only additions if new output)
- [ ] No new check without a real user case attached

<!-- If a box is unchecked, say why here — some changes legitimately need the
     discussion. Don't silently delete the line. -->

## Verification

```
python -m pytest tests/
```

<!-- Paste the result, including the corpus scoreboard line. -->

## Notes for the reviewer

<!-- Anything you're unsure about, or deliberately left out. -->
