# Stock Analysis — Python Pipeline & Agent Skill (v5.0)

Independent, data-driven stock analysis: weighted scoring, GPU-accelerated ML signals, Quantitative Analyst reports, backtesting, and structured JSON for trading-bot integration.

**This is your project** — a standalone Python codebase first. Optional agent skill packages live under `.grok/` for Grok Build (and compatible harnesses).

**Canonical code** lives in `scripts/` (signals, scoring, reports, dashboard, backtester, quant agent).

---

## Features

- **Configurable investor profiles** — Balanced, Value, Growth, Momentum (adjusts pillar weights automatically)
- **6-pillar weighted scoring** — Fundamentals, Technicals, Valuation, Sentiment, ESG, Risk (0–100 composite; Risk is scored, not cosmetic)
- **20+ quantitative signals** — DCF, Monte Carlo VaR/CVaR, RSI/MACD, SMA/ADX trend pack, LSTM, Chronos-2, multi-horizon ensemble, FinBERT, X/social, etc.
- **Quantitative Analyst agent** — structured report + conviction + debate contribution
- **Backtester** — point-in-time replay, policy, equity curve, exportable decisions
- **Risk management** — position sizing hooks, stop hints, auto-flagging
- **Multi-horizon forecasts** — 5d / 10d / 15d / 20d / 50d with median and weighted ensembles
- **Streamlit dashboard** — interactive exploration with Plotly charts
- **JSON signal export** — `signals_TICKER.json` for trading-bot consumption
- **Agent commands** — `/analyze-stock`, `/watchlist` (via `.grok/commands/`)

---

## Installation

```bash
git clone https://github.com/shahramk61/Stock_analysis.git
cd Stock_analysis
python -m pip install -r requirements.txt
```

Open the repo in Grok Build (or any agent) from this directory — project skills under `.grok/` load automatically.

---

## Python Pipeline Usage

```bash
# Full analysis (report + JSON)
python scripts/analyze.py AAPL --output both --profile Balanced

# JSON only (trading bot)
python scripts/analyze.py AAPL --output json --profile Growth

# Interactive dashboard
streamlit run scripts/dashboard.py

# Quantitative Analyst smoke test
python test_quant_analyst.py

# Backtest (fast mode recommended)
python scripts/backtest.py AAPL --start 2024-01-01 --fast --export

# Demo / no neural forecasts / relaxed policy for simulator visibility
python scripts/backtest.py AAPL --start 2024-06-01 --fast --no-forecasts --relaxed --debate --export
```

Optional: `--dynamic-weights` for out-of-sample ensemble weighting (~2× slower).  
Forecasts default to horizons **5d / 20d / 50d** for speed; full set available via code (`full_horizons=True`).

---

## Agent Usage (Grok)

### Analyze a single stock

```
/analyze-stock AAPL
```

### Compare multiple stocks

```
/analyze-stock AAPL MSFT NVDA
```

### Rank a watchlist

```
/watchlist AAPL MSFT NVDA GOOGL META AMZN
```

You can also ask in natural language: *“Analyze NVDA with the Growth profile”* — the `stock-analysis` skill will guide the run.

---

## Scoring Model

| Pillar | Balanced | Value | Growth | Momentum |
|---|---|---|---|---|
| Fundamentals | 25% | 20% | 30% | 15% |
| Technicals | 20% | 15% | 25% | 30% |
| Valuation | 20% | 30% | 15% | 15% |
| Sentiment | 10% | 10% | 10% | 15% |
| ESG | 10% | 10% | 5% | 10% |
| Risk | 15% | 15% | 15% | 15% |

Risk uses MC VaR, GARCH vol ratio, ATR clustering, Altman zone, and HMM regime.

| Score | Rating |
|---|---|
| 75–100 | Strong Buy |
| 60–74 | Buy |
| 50–59 | Hold/Watch |
| 35–49 | Caution |
| 0–34 | Avoid / Sell |

Human reports and JSON export use the same recommendation bands.

---

## Project Structure

```
scripts/
├── stock_signals.py      # Canonical signals (7-model ensemble, liquidity, etc.)
├── analyze.py, score.py, report.py, dashboard.py
├── backtest.py + backtest/   # Historical replay + policy + metrics
└── agents/quantitative_analyst/

.grok/
├── skills/stock-analysis/   # Agent skill (primary)
└── commands/                # /analyze-stock, /watchlist

SKILL.md, ROADMAP.md, requirements.txt
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for milestone status. Active focus: backtest validation before any live broker bridge.

---

## License

MIT — see [LICENSE](LICENSE).
