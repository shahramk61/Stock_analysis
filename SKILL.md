---
name: stock-analysis
description: >
  Analyze stocks with a 6-pillar weighted score, 20+ quantitative signals,
  Monte Carlo risk, multi-horizon forecasts, Quantitative Analyst reports,
  and optional backtests. Use when the user asks to analyze a ticker, rank a
  watchlist, run stock signals, or backtest the agent policy.
---

# Stock Analysis Skill v5.0

**Canonical code:** `scripts/` (never invent numbers — run the pipeline).

## Commands

```bash
# Full analysis
python scripts/analyze.py TICKER --profile [Balanced|Growth|Value|Momentum] --output [report|json|both]

# Dashboard
streamlit run scripts/dashboard.py

# Quant analyst smoke test
python test_quant_analyst.py

# Backtest
python scripts/backtest.py TICKER --start YYYY-MM-DD --fast --export [--debate]
```

## Profiles & scoring

Pillars: Fundamentals, Technicals, Valuation, Sentiment, ESG, Risk (0–100 overall).

| Score | Rating |
|---|---|
| 75–100 | Strong Buy |
| 60–74 | Buy |
| 50–59 | Hold/Watch |
| 35–49 | Caution |
| 0–34 | Avoid / Sell |

## Agent workflow

1. Confirm ticker(s) and optional profile (default **Balanced**).
2. Prefer running `python scripts/analyze.py …` for live numbers.
3. For multi-ticker ranking, score each then present a sorted table + Top 3.
4. Cite real pipeline outputs only — no fabricated prices, scores, or fundamentals.
5. For validation / paper trading research, use `scripts/backtest.py` with `--fast`.

## Key modules

| Path | Role |
|---|---|
| `scripts/stock_signals.py` | All quantitative signals |
| `scripts/score.py` | Pillar scoring |
| `scripts/report.py` | Human + JSON reports |
| `scripts/agents/quantitative_analyst/` | Quant Analyst agent |
| `scripts/backtest/` | Point-in-time backtester |

## Requirements

See `requirements.txt` (yfinance, pandas, numpy, torch optional for GPU signals, streamlit/plotly for dashboard, arch/hmmlearn for regime/vol).

## Version notes (v5.0+)

- Unified pipeline under `scripts/`
- Quantitative Analyst + structured conviction / debate contribution
- Backtesting foundation (as-of hist, policy, metrics, CLI) + risk filters + position sizing
- Risk pillar in overall score; RSI/MACD + SMA/ADX trend pack for agents
- Faster multi-horizon defaults (5/20/50d, Chronos cache, LSTM early stop, score dedupe)
- X/social sentiment hook for debates (`get_x_ticker_sentiment`)
