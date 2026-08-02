# Contributing

Thanks for helping improve Stock Analysis. Keep the pipeline **honest** (no invented metrics) and the **Execute** path stricter than Research labels.

## Workflow

1. Branch from `main`: `git checkout -b feature/short-description`
2. Make focused changes under `scripts/` and `tests/`
3. Run the relevant unit tests (see README)
4. Open a PR with: **what**, **why**, **how tested**, and any CLI flag changes

## Code guidelines

- **Canonical path:** `scripts/` only for production logic (avoid duplicate trees).
- **No look-ahead** in backtests: as-of slices only; never pass live `info` PE/ROE into replay.
- **Policy vs research:** score-band BUY must not bypass VaR / Bear / memory blocks.
- **Forecasts / Path C:** remain opt-in unless a PR includes calibration evidence and updates README defaults deliberately.
- Prefer pure helpers + unit tests for policy/scoring (see `tests/test_policy_leverage.py`).

## Tests to run before PR

Minimum for policy/scoring changes:

```bash
python tests/test_recommendation_dual.py
python tests/test_policy_leverage.py
python tests/test_backtest_engine.py
```

If you touch debate/handoff:

```bash
python tests/test_debate_session.py
python tests/test_decision_memory.py
```

If you touch multi-horizon / forecast defaults:

```bash
python tests/test_gme_forecast_policy_audit.py
```

## Do not commit

- API keys, tokens, `.env` with secrets  
- `lightning_logs/`, model weight dumps  
- `signals_*.json`, `backtest_decisions_*.json`  
- `decisions/handoff_*.json`, `decisions/live_*.json`, `decisions/debate_*.json` (regenerate)  
- Bulky `journal/runs/*.json`  

Use `.gitignore`; keep `decisions/.gitkeep` and `journal/runs/.gitkeep` so empty dirs exist.

## PR description template

```markdown
### Summary
…

### Motivation
…

### Test plan
- [ ] unit tests listed above
- [ ] manual CLI (command …)
```

## License

By contributing, you agree your changes are under the same MIT license as the project.
