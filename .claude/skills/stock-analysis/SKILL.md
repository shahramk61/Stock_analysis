---
name: stock-analysis
description: Analyze stocks using weighted scoring across fundamentals, technicals, and sentiment. Includes risk management recommendations. Use when users want to evaluate a stock, compare equities, assess risk, or build a watchlist.
allowed-tools: Read, Write, Bash, WebFetch, WebSearch
---

# Stock Analysis Skill

Perform comprehensive stock analysis using a weighted multi-factor scoring model with integrated risk management.

## Scoring Model

Each stock is scored 0–100 across four pillars, then combined into a weighted composite:

| Pillar | Weight | Key Metrics |
|---|---|---|
| Fundamentals | 35% | P/E, P/B, EPS growth, revenue growth, debt/equity, FCF yield |
| Technicals | 25% | RSI, MACD, 50/200-day MA, volume trend, price momentum |
| Valuation | 25% | DCF implied upside, P/S vs sector, EV/EBITDA |
| Sentiment | 15% | Analyst ratings, earnings surprise history, insider activity |

**Composite Score = 0.35×F + 0.25×T + 0.25×V + 0.15×S**

## Score Interpretation

| Score | Rating | Action |
|---|---|---|
| 80–100 | Strong Buy | High conviction entry |
| 65–79 | Buy | Favorable risk/reward |
| 50–64 | Hold/Watch | Monitor for catalyst |
| 35–49 | Caution | Reduce or avoid |
| 0–34 | Avoid | High risk, poor fundamentals |

## Risk Management Framework

For every analysis, assess and report:

1. **Position Sizing**: Based on composite score and volatility (beta/ATR)
   - Score ≥80 and beta <1.2: up to 5% portfolio weight
   - Score 65–79 or beta 1.2–1.8: up to 3% portfolio weight
   - Score 50–64 or beta >1.8: up to 1.5% portfolio weight
   - Score <50: avoid or <0.5%

2. **Stop-Loss Levels**
   - Conservative: 1.5× ATR below entry
   - Standard: 2× ATR below entry
   - Aggressive: below nearest key support level

3. **Risk/Reward Ratio**: Only recommend entry if R/R ≥ 2:1
   - Target: DCF fair value or next resistance level
   - Stop: per stop-loss framework above

4. **Key Risk Flags** (auto-flag these):
   - Debt/Equity > 2.0
   - Negative FCF for 2+ consecutive years
   - RSI > 75 (overbought) or < 25 (oversold)
   - Earnings miss 2+ consecutive quarters
   - Insider selling > 5% of float in past 90 days
   - Beta > 2.0

## Workflow

### Single Stock Analysis

1. Gather data (use WebSearch/WebFetch for live data or ask user to provide):
   - Income statement, balance sheet, cash flow (trailing 12 months)
   - Current price, 52-week range, beta, ATR
   - Analyst consensus, recent earnings surprises
   - RSI, MACD, moving averages

2. Score each pillar (0–100) with brief rationale

3. Calculate composite score

4. Apply risk management framework

5. Output structured report (see template below)

### Stock Comparison / Watchlist

When comparing multiple stocks:
- Score all stocks using the same framework
- Rank by composite score
- Highlight top pick and explain differentiation
- Flag any risk disqualifiers

## Output Template

```
## Stock Analysis: [TICKER] — [Company Name]
**Date**: [date] | **Price**: $[price] | **Sector**: [sector]

### Pillar Scores
| Pillar | Score | Key Drivers |
|---|---|---|
| Fundamentals (35%) | [0-100] | [2-3 bullet points] |
| Technicals (25%) | [0-100] | [2-3 bullet points] |
| Valuation (25%) | [0-100] | [2-3 bullet points] |
| Sentiment (15%) | [0-100] | [2-3 bullet points] |

**Composite Score**: [score]/100 → **[Rating]**

### Risk Management
- **Suggested Position Size**: [X]% of portfolio
- **Stop-Loss**: $[price] ([X]% below entry, [N]× ATR)
- **Price Target**: $[price] ([X]% upside)
- **Risk/Reward**: [X]:1

### Risk Flags
[List any flagged risks, or "None identified"]

### Summary
[2-3 sentence investment thesis and key catalysts to watch]
```

## Data Sources

When live data is needed, use WebSearch to find recent data from:
- SEC EDGAR filings (earnings, 10-K/10-Q)
- Yahoo Finance, Finviz, Macrotrends for historical metrics
- CNBC, Seeking Alpha for analyst sentiment
- OpenInsider for insider transaction data

Always note the data date and any limitations (e.g., using TTM vs forward estimates).
