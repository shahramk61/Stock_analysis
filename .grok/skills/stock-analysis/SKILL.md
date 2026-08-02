---
name: stock-analysis
description: >
  Analyze one or more stocks with weighted 6-pillar scoring, quantitative
  signals, risk metrics, dual Research/Execute labels, optional multi-horizon
  forecasts, and walk-forward backtests. Use for /analyze-stock, watchlist
  ranking, ticker deep-dives, or agent policy validation.
---

# Stock Analysis (project skill)

**Owner project:** this repo. Canonical Python lives in `scripts/`.  
**Agent prompts:** `scripts/agents/PROMPTS.md`  
**Quant schema:** `scripts/agents/quantitative_analyst/schemas.py`  
**Onboarding:** `docs/ONBOARDING.md`

## When to use

- User names a ticker or watchlist
- User asks for score, buy/hold view, DCF, risk, or quant report
- User wants a backtest of the scoring/quant agent

## How to run (always prefer real code)

```bash
# Single-name analysis
python scripts/analyze.py TICKER --profile Balanced --output both

# Fast backtest (forecasts OFF by default; next-open fill, daily stops, flat exits)
python scripts/backtest.py TICKER --start 2024-01-01 --fast --export --validate

# Opt-in neural forecasts / Path C multi-horizon entry (research)
python scripts/backtest.py TICKER --start 2024-06-01 --forecasts --export
python scripts/backtest.py TICKER --start 2024-06-01 --forecasts --multi-horizon-entry --export

# Quant smoke + schema/golden tests
python test_quant_analyst.py
python tests/test_quant_schema.py
python tests/test_no_lookahead.py
python tests/test_backtest_engine.py
python tests/test_recommendation_dual.py
python tests/test_policy_leverage.py
```

Profiles: `Balanced` | `Growth` | `Value` | `Momentum`.

## Output rules (hard)

1. **Never invent** prices, fundamentals, scores, VaR, regime, or recommendations.
2. Run the real pipeline; cite only stdout / signals JSON / quant structured fields.
3. If data is missing, say **unknown / not provided** — do not guess.
4. Map overall score to **Research** labels: Strong Buy ≥75, Buy ≥60, Hold ≥50, Caution ≥35, else Avoid/Sell.
5. **Execute** comes from policy (`policy_hint`) — Research BUY is **not** a trade ticket when Execute is FLAT.
6. **Always surface risk** when present: high MC VaR, Bear HMM regime, distress/Grey Altman Z.
7. Quant **conviction** is only **High | Medium | Low**.
8. Multi-ticker: rank by overall score; Top 3 + risk disqualifiers.
9. Role boundary: Quant Analyst is a **data provider**, not a free-form trader.

## Structured handoff keys

- `dual_recommendation` (Research vs Execute + `policy_conflict`)
- `policy_hint.action` / `conviction` / `suggested_risk_pct`
- `quantitative_conviction`, `quantitative_signals.risk.var_95`, `regime.regime`
- `quantitative_signals.classic` / `trend` / `adx`

## Useful entry points

| Task | Entry |
|------|--------|
| Full report | `scripts/analyze.py` |
| Dual labels | `scripts/recommendation.py` |
| Quant agent | `scripts/agents/quantitative_analyst/` |
| Backtest | `scripts/backtest.py` |
| Handoff | `scripts/prepare_decision_handoff.py` |
| Dashboard | `streamlit run scripts/dashboard.py` |
| Grok decision | skill **stock-decision** / `/decide-stock` |

See root `README.md`, `docs/ONBOARDING.md`, `docs/grok-hooks.md`.
