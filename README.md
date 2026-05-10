# Stock Analysis — Claude Code Skill

A Claude Code skill for comprehensive, data-driven stock analysis. Uses a configurable weighted scoring model across four pillars — fundamentals, technicals, valuation, and sentiment — with integrated risk management, sector/peer comparison, and multi-horizon recommendations.

---

## Features

- **Configurable investor profiles** — Balanced, Value, Growth, Momentum, Income (adjusts pillar weights automatically)
- **4-pillar weighted scoring** — 0–100 composite score with emoji ratings
- **Risk management** — position sizing, ATR-based stop-losses, R/R ratio check, auto-flagging of 8 risk conditions
- **Sector & peer comparison** — benchmarks the stock against 3–5 peers and sector averages
- **Multi-horizon recommendations** — separate Buy/Hold/Avoid for Swing, Intermediate, and Long-term
- **Catalyst calendar** — earnings date, ex-dividend, upcoming events
- **Multi-stock comparison** — score and rank multiple tickers in one command
- **Watchlist ranking** — fast-score a list of tickers and get a ranked table
- **Data integrity guardrails** — never invents numbers; flags missing data explicitly

---

## Installation

This skill works inside any Claude Code project. Copy the `.claude/` folder into your project root:

```bash
git clone https://github.com/shahramk61/Stock_analysis.git
cp -r Stock_analysis/.claude /your/project/root/
```

Or use it standalone by opening this repo directly in Claude Code:

```bash
cd Stock_analysis
claude
```

---

## Usage

### Analyze a single stock

```
/analyze-stock AAPL
```

Claude will ask your investor profile, then deliver a full report with pillar scores, risk management, peer comparison, and catalyst calendar.

### Compare multiple stocks

```
/analyze-stock AAPL MSFT NVDA
```

Scores all three, builds a ranking table, and identifies the top pick with a comparison summary.

### Rank a watchlist

```
/watchlist AAPL MSFT NVDA GOOGL META AMZN
```

Fast-scores the entire list and returns a ranked table with composite scores, ratings, one-line theses, and risk flags.

---

## Scoring Model

Each stock is scored 0–100 across four pillars, then combined using profile weights:

| Pillar | Balanced | Value | Growth | Momentum | Income |
|---|---|---|---|---|---|
| Fundamentals | 35% | 40% | 40% | 20% | 35% |
| Technicals | 25% | 15% | 20% | 40% | 20% |
| Valuation | 25% | 35% | 20% | 20% | 30% |
| Sentiment | 15% | 10% | 20% | 20% | 15% |

### Score → Rating

| Score | Rating |
|---|---|
| 80–100 | 🟢🟢 Strong Buy |
| 65–79 | 🟢 Buy |
| 50–64 | 🟡 Hold/Watch |
| 35–49 | 🔴 Caution |
| 0–34 | 🔴🔴 Avoid |

---

## Example Output (abbreviated)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 STOCK ANALYSIS: AAPL — Apple Inc.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Date: 2026-05-10  |  💲 Price: $213.49  |  🏭 Sector: Technology
🎯 Investor Profile: Growth

## Executive Summary
Apple continues to dominate consumer hardware and services, with Services
revenue growing 14% YoY and expanding margins offsetting iPhone plateau risk.
The stock trades at a premium but justified by its capital return program and
AI integration runway; the key risk is China revenue exposure (~17% of sales).

Composite Score: 74/100 🟢 → Buy

| Pillar | Weight | Score | Drivers |
|---|---|---|---|
| 📈 Fundamentals | 40% | 78 | EPS +9% YoY; FCF yield 3.8%; D/E 1.8 (flagged) |
| 📉 Technicals   | 20% | 68 | RSI=54; above 50MA, below 200MA; RS neutral |
| 💰 Valuation    | 20% | 65 | PEG=2.8; Fwd P/E=28; DCF upside ~12% |
| 🗣 Sentiment    | 20% | 82 | 31 Buy / 8 Hold / 1 Sell; short int=0.7% |

🚩 Risk Flags
- ⚠️ Debt/Equity = 1.8 (approaching 2.0 threshold)
- ⚠️ China revenue concentration risk

Multi-Horizon:
| Horizon | Rating | Rationale |
|---|---|---|
| 🏃 Swing (1–3 mo) | Hold | Near-term resistance at $220; wait for pullback |
| 📈 Intermediate   | Buy  | Services margin expansion drives EPS beat likely |
| 🏦 Long-term      | Buy  | AI ecosystem lock-in and capital return support thesis |
```

---

## Risk Management

Every analysis includes:

- **Position sizing** based on composite score + beta
- **Stop-loss** at 1.5–2× ATR below entry
- **Price target** from DCF or technical resistance
- **R/R ratio** (only recommends entry at ≥ 2:1)
- **8 auto-flagged risk conditions**: high debt, negative FCF, RSI extremes, consecutive earnings misses, insider selling, high beta, high short interest, negative news sentiment

---

## Project Structure

```
.claude/
├── skills/
│   └── stock-analysis/
│       └── SKILL.md          # Full skill definition
└── commands/
    ├── analyze-stock.md      # /analyze-stock TICKER [...]
    └── watchlist.md          # /watchlist TICKER1 TICKER2 ...
README.md
```

---

## Roadmap

- [ ] Monte Carlo simulation for price target ranges
- [ ] ESG/Quality pillar (optional 5–10% weight)
- [ ] Alert logic: re-analyze when price hits target or earnings approach
- [ ] Export analysis to PDF or markdown file
- [ ] Claude Project integration with uploaded 10-Ks and earnings transcripts
