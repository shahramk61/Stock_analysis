# Stock Analysis — Claude Code Skill & Python Pipeline (v5.0)

Comprehensive, data-driven stock analysis with a configurable weighted scoring model, GPU-accelerated ML signals, and structured JSON output for trading-bot integration.

**Canonical code** lives in `scripts/` (signals, scoring, reports, dashboard). The Claude skill under `.claude/skills/stock-analysis/` re-exports from there.

---

## Features

- **Configurable investor profiles** — Balanced, Value, Growth, Momentum (adjusts pillar weights automatically)
- **6-pillar weighted scoring** — Fundamentals, Technicals, Valuation, Sentiment, ESG, Risk (0–100 composite)
- **20+ quantitative signals** — DCF, Monte Carlo VaR/CVaR, LSTM, Chronos-2, 7-model ensemble, FinBERT, etc.
- **Risk management** — position sizing, ATR-based stop-losses, R/R ratio, auto-flagging
- **Multi-horizon forecasts** — 5d / 10d / 15d / 20d / 50d with median and weighted ensembles
- **Streamlit dashboard** — interactive exploration with Plotly charts
- **JSON signal export** — `signals_TICKER.json` for trading-bot consumption
- **Claude Code commands** — `/analyze-stock`, `/watchlist`

---

## Installation

```bash
git clone https://github.com/shahramk61/Stock_analysis.git
cd Stock_analysis
python -m pip install -r requirements.txt
```

For Claude Code only, copy `.claude/` into your project root, or open this repo directly:

```bash
claude
```

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
```

Optional: `--dynamic-weights` for out-of-sample ensemble weighting (~2× slower).

---

## Claude Code Usage

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

| Score | Rating |
|---|---|
| 75–100 | Strong Buy |
| 60–74 | Buy |
| 50–59 | Hold/Watch |
| 35–49 | Caution |
| 0–34 | Avoid |

---

## Project Structure

```
scripts/
├── stock_signals.py      # Canonical signals (7-model ensemble, etc.)
├── analyze.py, score.py, report.py, dashboard.py
└── agents/quantitative_analyst/

.claude/
├── skills/stock-analysis/   # Skill definition + shims → scripts/
└── commands/                # /analyze-stock, /watchlist

SKILL.md, ROADMAP.md, requirements.txt
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for milestone status. Phase 2: integrate Quantitative Analyst into TradingAgents.

---

## License

MIT — see [LICENSE](LICENSE).