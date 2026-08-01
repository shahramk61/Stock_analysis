---
name: stock-analysis
description: >
  Analyze one or more stocks with weighted 6-pillar scoring, quantitative
  signals, risk metrics, multi-horizon forecasts, and optional backtests.
  Use for /analyze-stock, watchlist ranking, ticker deep-dives, or agent policy validation.
---

# Stock Analysis (project skill)

**Owner project:** this repo. Canonical Python lives in `scripts/`.

## When to use

- User names a ticker or watchlist
- User asks for score, buy/hold view, DCF, risk, or quant report
- User wants a backtest of the scoring/quant agent

## How to run (always prefer real code)

```bash
# Single-name analysis
python scripts/analyze.py TICKER --profile Balanced --output both

# Fast backtest
python scripts/backtest.py TICKER --start 2024-01-01 --fast --export

# Quant-only smoke test
python test_quant_analyst.py
```

Profiles: `Balanced` | `Growth` | `Value` | `Momentum`.

## Output rules

1. **Never invent** prices, fundamentals, scores, or recommendations.
2. Use pipeline stdout / JSON (`signals_TICKER.json`) as the source of truth.
3. Map overall score to: Strong Buy ≥75, Buy ≥60, Hold ≥50, Caution ≥35, else Avoid/Sell.
4. Surface risk flags (high VaR, Bear regime, distress Z-score) even on constructive views.
5. Multi-ticker: rank by overall score; call out Top 3 and disqualifiers.

## Useful entry points

| Task | Entry |
|---|---|
| Full report | `scripts/analyze.py` |
| Scoring only | `scripts/score.py` via analyze |
| Quant agent | `scripts/agents/quantitative_analyst/quantitative_analyst.py` |
| Backtest | `scripts/backtest.py` |
| Dashboard | `streamlit run scripts/dashboard.py` |

See root `README.md` and `ROADMAP.md` for architecture and milestone status.
