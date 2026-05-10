---
name: stock-analysis
description: Analyze stocks using configurable weighted scoring across fundamentals, technicals, valuation, and sentiment. Includes sector/peer comparison, risk management, multi-horizon recommendations, and catalyst calendar. Use when users want to evaluate a stock, compare equities, assess risk, or rank a watchlist.
allowed-tools: Read, Write, Bash, WebFetch, WebSearch
version: 2.0
last-updated: 2026-05-10
---

# Stock Analysis Skill v2.0

Comprehensive stock analysis using a configurable multi-factor weighted scoring model with integrated risk management, peer comparison, and multi-horizon recommendations.

---

## Step 0 — Investor Profile (Ask First)

Before analyzing, ask the user their investor style if not already stated. This sets the scoring weights:

| Profile | Fundamentals | Technicals | Valuation | Sentiment | Best For |
|---|---|---|---|---|---|
| **Balanced** (default) | 35% | 25% | 25% | 15% | General / mixed portfolio |
| **Value** | 40% | 15% | 35% | 10% | Undervalued, dividend-focused |
| **Growth** | 40% | 20% | 20% | 20% | High-growth, disruption plays |
| **Momentum** | 20% | 40% | 20% | 20% | Trend-following, short-term |
| **Income** | 35% | 20% | 30% | 15% | Yield-focused, conservative |

If the user skips this, default to **Balanced**.

---

## Scoring Model

Score each pillar 0–100, then apply the chosen weights:

**Composite Score = w_F×F + w_T×T + w_V×V + w_S×S**

### Pillar 1 — Fundamentals

| Metric | What to assess |
|---|---|
| EPS growth (YoY & 3yr CAGR) | Positive and accelerating = higher score |
| Revenue growth (YoY & 3yr CAGR) | Consistent double-digit growth preferred |
| Gross & operating margin trend | Expanding margins = strong moat |
| Debt/Equity ratio | <0.5 strong, >2.0 flag |
| Free Cash Flow yield | Positive FCF, FCF > net income preferred |
| Return on Equity (ROE) | >15% solid, >25% excellent |

### Pillar 2 — Technicals

| Metric | What to assess |
|---|---|
| RSI (14-day) | 40–60 neutral, >75 overbought, <25 oversold |
| MACD | Signal crossover direction and histogram trend |
| 50-day / 200-day MA | Price above both = bullish; death cross = bearish |
| Relative Strength vs sector | Stock outperforming its sector index = bullish |
| ATR% (volatility) | ATR/price × 100; higher = more volatile, adjust position size |
| Volume trend | Accumulation (rising volume on up days) = bullish |

### Pillar 3 — Valuation

| Metric | What to assess |
|---|---|
| Forward P/E | **Primary metric.** Compare to sector median, 5yr avg, and peers. Discount if >20% above both. |
| Trailing P/E | Context for Forward P/E; wide gap signals expected inflection in earnings |
| PEG ratio | <1.0 potentially undervalued for growth, >2.0 expensive; use forward EPS growth |
| P/S ratio | Compare to sector; high P/S requires >20% revenue growth to justify |
| EV/EBITDA | <10 value territory; most comparable across capital structures |
| DCF implied upside | >20% upside = good; >40% = undervalued; state discount rate and assumptions |
| Price vs 52-week range | Near 52w low with strong fundamentals = opportunity; near high = lower margin of safety |

### Pillar 4 — Sentiment

| Metric | What to assess |
|---|---|
| Analyst consensus | Strong Buy/Buy % vs Hold/Sell; # of coverage changes |
| Earnings surprise history | Beat last 2–4 quarters = positive momentum |
| Insider activity | Net buying vs selling; flag >5% float sold in 90 days |
| Short interest % | >20% = heavy short, potential squeeze or justified |
| News sentiment | Recent headlines: positive catalyst, scandal, regulatory risk |

---

## Score Interpretation

| Score | Emoji | Rating | Action |
|---|---|---|---|
| 80–100 | 🟢🟢 | Strong Buy | High conviction entry |
| 65–79 | 🟢 | Buy | Favorable risk/reward |
| 50–64 | 🟡 | Hold/Watch | Monitor for catalyst |
| 35–49 | 🔴 | Caution | Reduce or avoid |
| 0–34 | 🔴🔴 | Avoid | High risk, poor fundamentals |

---

## Risk Management Framework

### Position Sizing

| Composite Score | Beta | Max Portfolio Weight |
|---|---|---|
| ≥80 | <1.2 | 5% |
| 65–79 | any | 3% |
| 50–64 | <1.8 | 1.5% |
| <50 | any | 0% (avoid) |

If the user provides their total risk budget or current portfolio %, scale suggestions proportionally.

### Stop-Loss Levels

- **Conservative**: entry − 1.5× ATR
- **Standard**: entry − 2× ATR
- **Aggressive**: just below nearest key support

### Risk/Reward Rule

Only recommend entry if R/R ≥ 2:1.
- **Target**: DCF fair value or next key resistance
- **Stop**: per framework above

### 🚩 Auto-Flag These Risk Conditions

Flag any of the following prominently in the report:

- Debt/Equity > 2.0
- Negative FCF for 2+ consecutive years
- RSI > 75 (overbought) or < 25 (oversold)
- Earnings miss 2+ consecutive quarters
- Insider selling > 5% of float in past 90 days
- Beta > 2.0
- Short interest > 20% of float
- Negative news sentiment (regulatory, legal, or reputational risk)

---

## Sector & Peer Comparison

For every analysis, compare the target stock against 3–5 peers and the sector average:

1. Identify 3–5 direct competitors or sector peers
2. Pull key metrics for each: P/E, P/S, EV/EBITDA, revenue growth, gross margin, ROE
3. Score the target relative to peers (above/below sector median)
4. Summarize in a compact table showing where the stock stands vs. the group

---

## Multi-Horizon Recommendations

Provide a separate recommendation for each time horizon:

| Horizon | Timeframe | Key Drivers |
|---|---|---|
| 🏃 Swing | 1–3 months | Technicals, momentum, near-term catalyst |
| 📈 Intermediate | 6–18 months | Fundamentals + valuation, earnings trend |
| 🏦 Long-term | 3+ years | Business quality, moat, sector tailwinds |

Each horizon gets its own Buy/Hold/Avoid rating and 1-sentence rationale.

---

## Catalyst Calendar

Always include upcoming events:
- Next earnings date (and analyst EPS estimate)
- Ex-dividend date (if applicable)
- Upcoming conferences, product launches, or regulatory decisions
- Analyst day or management guidance updates

---

## Data Integrity Rules

> **CRITICAL — Never violate these:**
>
> 1. **Never invent numbers.** If a metric is unavailable, write `Data unavailable` and note it explicitly.
> 2. **Always cite source + date** for every data point used (e.g., "Yahoo Finance, 2026-05-09").
> 3. **If WebFetch fails**, state clearly: "Live data unavailable — the following uses [source/assumption]. Please verify before trading."
> 4. **Directional estimates only** when data is missing: "Revenue growth appears positive based on [X], but exact figure unavailable."
> 5. **Never make a Buy recommendation** when more than 2 key metrics are missing.
> 6. **Price target guardrail**: Do not set a price target more than ±30% from current price unless you provide explicit, data-backed justification (e.g., confirmed DCF, imminent catalyst, or comparable acquisition premium). Flag any target beyond this range with ⚠️.

---

## Workflow

### Single Stock

1. Ask investor profile (if not given)
2. Gather data via WebSearch/WebFetch — cite each source
3. Score all four pillars with bullet rationale
4. Run risk management checks, flag any 🚩 conditions
5. Run sector/peer comparison
6. Build multi-horizon recommendations
7. Pull catalyst calendar
8. Output the full report using the template below

### Multi-Stock Comparison (`/analyze-stock AAPL MSFT NVDA`)

1. Score each stock in parallel using the same profile and weights
2. Build a ranking table sorted by composite score
3. Highlight the top pick with a "Why this one over the others" paragraph
4. Flag any risk disqualifiers that would eliminate a stock regardless of score

### Watchlist Ranking (`/watchlist`)

- Accept a list of tickers
- Score each with condensed analysis (fundamentals + valuation only for speed)
- Output ranked table with composite score, rating, and one-line thesis
- Mark any 🚩 flagged stocks

---

## Output Template

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 STOCK ANALYSIS: [TICKER] — [Company Name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Date: [date]  |  💲 Price: $[price]  |  🏭 Sector: [sector]
🎯 Investor Profile: [Balanced / Value / Growth / Momentum / Income]

## Executive Summary
[3-sentence thesis: what the company does, why the score is what it is,
and the single most important catalyst or risk to watch.]

Composite Score: [score]/100 [emoji] → [Rating]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Pillar Scores
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Pillar | Weight | Score | Drivers |
|---|---|---|---|
| 📈 Fundamentals | [w]% | [0-100] | EPS +X% YoY; FCF yield Y%; D/E Z |
| 📉 Technicals   | [w]% | [0-100] | RSI=X; above/below 50/200MA; RS vs sector |
| 💰 Valuation    | [w]% | [0-100] | PEG=X; Forward P/E=Y; DCF upside=Z% |
| 🗣 Sentiment    | [w]% | [0-100] | X Buy / Y Hold / Z Sell; short int=N% |

Composite Score = [formula] = [score]/100

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Risk Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 💼 Suggested Position Size: [X]% of portfolio
- 🛑 Stop-Loss: $[price] ([N]× ATR = [X]% below entry)
- 🎯 Price Target: $[price] ([X]% upside, [basis])
- ⚖️ Risk/Reward: [X]:1 [✅ meets 2:1 minimum / ❌ does not meet threshold]

### 🚩 Risk Flags
[List flagged conditions, or "✅ No flags identified"]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Sector & Peer Comparison
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Company | P/E | PEG | Rev Growth | Gross Margin | ROE | Score |
|---|---|---|---|---|---|---|
| **[TICKER]** | | | | | | **[score]** |
| [Peer 1]    | | | | | | |
| [Peer 2]    | | | | | | |
| Sector Avg  | | | | | | |

[1-sentence conclusion: how the stock ranks vs peers]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Multi-Horizon Recommendations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Horizon | Rating | Rationale |
|---|---|---|
| 🏃 Swing (1–3 mo)       | [Buy/Hold/Avoid] | [1 sentence] |
| 📈 Intermediate (6–18 mo) | [Buy/Hold/Avoid] | [1 sentence] |
| 🏦 Long-term (3+ yr)    | [Buy/Hold/Avoid] | [1 sentence] |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Catalyst Calendar
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 📣 Next Earnings: [date] (est. EPS: $[X])
- 💵 Ex-Dividend Date: [date or N/A]
- 📅 Upcoming Events: [conferences, product launches, regulatory decisions]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Data Sources
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[List each source with date, e.g.:]
- Yahoo Finance (2026-05-09): price, P/E, beta
- SEC EDGAR 10-Q (2026-03-31): revenue, FCF, D/E
- OpenInsider (2026-05-01): insider transactions
[Note any missing data or assumptions made]
```

---

## Data Sources Reference

| Data Type | Source |
|---|---|
| Financials (income, balance, cash flow) | SEC EDGAR, Macrotrends |
| Live price, ratios, beta | Yahoo Finance, Finviz |
| Analyst ratings & estimates | Seeking Alpha, Finviz |
| Insider transactions | OpenInsider |
| Short interest | Finviz, Nasdaq short interest |
| News sentiment | CNBC, Reuters, Seeking Alpha headlines |
| Sector comparisons | Finviz screener, Macrotrends |
