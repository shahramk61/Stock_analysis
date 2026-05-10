---
name: stock-analysis
description: Analyze stocks using configurable weighted scoring across fundamentals, technicals, valuation, sentiment, and optional ESG/quality. Includes Monte Carlo price simulation, sector/peer comparison, historical backtesting, alert logic, risk management, multi-horizon recommendations, and one-click export. Use when users want to evaluate a stock, compare equities, assess risk, or rank a watchlist.
allowed-tools: Read, Write, Bash, WebFetch, WebSearch
version: 3.0
last-updated: 2026-05-10
---

# Stock Analysis Skill v3.0

Comprehensive stock analysis using a configurable multi-factor scoring model with Monte Carlo simulation, backtesting, ESG/quality pillar, alert logic, and report export.

---

## Step 0 — Investor Profile (Ask First)

Ask the user their investor style before analyzing. This sets pillar weights.

**Base profiles (4-pillar):**

| Profile | Fundamentals | Technicals | Valuation | Sentiment | Best For |
|---|---|---|---|---|---|
| **Balanced** (default) | 35% | 25% | 25% | 15% | General / mixed portfolio |
| **Value** | 40% | 15% | 35% | 10% | Undervalued, dividend-focused |
| **Growth** | 40% | 20% | 20% | 20% | High-growth, disruption plays |
| **Momentum** | 20% | 40% | 20% | 20% | Trend-following, short-term |
| **Income** | 35% | 20% | 30% | 15% | Yield-focused, conservative |

**ESG toggle:** Ask if the user wants the ESG/Quality pillar included. If yes, subtract 2pp from each base pillar and add a 5th pillar at 8%:

| Profile | Fundamentals | Technicals | Valuation | Sentiment | ESG/Quality |
|---|---|---|---|---|---|
| Balanced + ESG | 33% | 23% | 23% | 13% | 8% |
| Value + ESG | 38% | 13% | 33% | 8% | 8% |
| Growth + ESG | 38% | 18% | 18% | 18% | 8% |
| Momentum + ESG | 18% | 38% | 18% | 18% | 8% |
| Income + ESG | 33% | 18% | 28% | 13% | 8% |

If the user skips profile selection, default to **Balanced** with no ESG.

---

## Scoring Model

Score each pillar 0–100, then apply weights:

**Composite Score = w_F×F + w_T×T + w_V×V + w_S×S [+ w_E×E if ESG enabled]**

### Pillar 1 — Fundamentals

| Metric | What to assess |
|---|---|
| EPS growth (YoY & 3yr CAGR) | Positive and accelerating = higher score |
| Revenue growth (YoY & 3yr CAGR) | Consistent double-digit growth preferred |
| Gross & operating margin trend | Expanding margins = strong moat |
| Debt/Equity ratio | <0.5 strong, >2.0 flag |
| Free Cash Flow yield | Positive FCF; FCF > net income preferred |
| Return on Equity (ROE) | >15% solid, >25% excellent |

### Pillar 2 — Technicals

| Metric | What to assess |
|---|---|
| RSI (14-day) | 40–60 neutral, >75 overbought, <25 oversold |
| MACD | Signal crossover direction and histogram trend |
| 50-day / 200-day MA | Price above both = bullish; death cross = bearish |
| Relative Strength vs sector | Outperforming sector index = bullish |
| ATR% (volatility) | ATR/price × 100; record this — used in Monte Carlo and stop-loss |
| Volume trend | Accumulation (rising volume on up days) = bullish |

### Pillar 3 — Valuation

| Metric | What to assess |
|---|---|
| Forward P/E | **Primary metric.** Compare to sector median, 5yr avg, and peers. Discount score if >20% above both. |
| Trailing P/E | Context for Forward P/E; wide gap signals expected earnings inflection |
| PEG ratio | <1.0 potentially undervalued for growth, >2.0 expensive; use forward EPS growth |
| P/S ratio | Compare to sector; high P/S requires >20% revenue growth to justify |
| EV/EBITDA | <10 value territory; most comparable across capital structures |
| DCF implied upside | >20% good; >40% undervalued; always state discount rate and terminal growth rate |
| Price vs 52-week range | Near 52w low with strong fundamentals = opportunity; near high = lower margin of safety |

### Pillar 4 — Sentiment

| Metric | What to assess |
|---|---|
| Analyst consensus | Strong Buy/Buy % vs Hold/Sell; note any recent rating changes |
| Earnings surprise history | Beat last 2–4 quarters = positive momentum |
| Insider activity | Net buying vs selling; flag >5% float sold in past 90 days |
| Short interest % | >20% = heavy short (potential squeeze or justified concern) |
| News sentiment | Recent headlines: positive catalyst, scandal, regulatory risk |

### Pillar 5 — ESG / Quality (Optional)

Only score this pillar if the user opted in during Step 0.

| Metric | What to assess |
|---|---|
| Economic Moat | Wide / Narrow / None — use Morningstar or analyst reports |
| Governance | Insider ownership %, board independence, dual-class share structure |
| Piotroski F-Score (0–9) | Derived from financial statements; >7 strong quality, <3 distressed |
| ROIC trend | Improving / stable / declining over 3 years |
| ESG controversies | Recent environmental, social, or regulatory controversies |

Scoring guide: Moat=Wide (+30 pts), F-Score>7 (+20 pts), improving ROIC (+20 pts), clean controversies (+15 pts), good governance (+15 pts). Deduct for each negative.

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

If the user provides their total risk budget or current portfolio %, scale proportionally.

### Stop-Loss Levels

- **Conservative**: entry − 1.5× ATR
- **Standard**: entry − 2× ATR
- **Aggressive**: just below nearest key support

### Risk/Reward Rule

Only recommend entry if R/R ≥ 2:1.
- **Target**: DCF fair value or next key resistance
- **Stop**: per framework above

### 🚩 Auto-Flag These Risk Conditions

- Debt/Equity > 2.0
- Negative FCF for 2+ consecutive years
- RSI > 75 (overbought) or < 25 (oversold)
- Earnings miss 2+ consecutive quarters
- Insider selling > 5% of float in past 90 days
- Beta > 2.0
- Short interest > 20% of float
- Negative news sentiment (regulatory, legal, or reputational risk)

---

## Monte Carlo Price Simulation

Run for every Intermediate and Long-term horizon recommendation. Claude calculates this directly using the log-normal approximation — no code execution needed.

### Inputs

| Input | How to derive |
|---|---|
| Current price S₀ | Live price |
| Annual volatility σ | ATR% × √252 (ATR% = ATR/price × 100) |
| Annual drift μ | Map composite score → drift using table below |
| Horizon T | Swing=63 days, Intermediate=365 days, Long-term=1095 days |

**Score → Expected Annual Drift:**

| Composite Score | Annual Drift μ |
|---|---|
| 80–100 | +25% to +35% |
| 65–79 | +15% to +25% |
| 50–64 | +5% to +15% |
| 35–49 | −5% to +5% |
| 0–34 | −20% to −5% |

Use midpoint of range (e.g. score 72 → μ = +20%).

### Formulas (Log-Normal Approximation)

All prices below use: **α = (μ − σ²/2) × T/252** and **β = σ × √(T/252)**

```
Median target    = S₀ × exp(α)
10th percentile  = S₀ × exp(α − 1.28 × β)    ← downside scenario
90th percentile  = S₀ × exp(α + 1.28 × β)    ← upside scenario

P(gain > +20%)   = 1 − Φ((ln(1.20) − α) / β)
P(stop-loss hit) = Φ((ln(stop/S₀) − α) / β)
P(new ATH)       = 1 − Φ((ln(ATH/S₀) − α) / β)
```

Where Φ is the standard normal CDF. Use these approximations:
- Φ(0) = 50%, Φ(0.5) = 69%, Φ(1.0) = 84%, Φ(1.28) = 90%
- Φ(1.5) = 93%, Φ(2.0) = 98%, Φ(−x) = 1 − Φ(x)

### Guardrails

- If σ > 60% (annualized), flag: ⚠️ Extreme volatility — simulation less reliable; widen percentile bands.
- If T > 3 years, note: "Long horizons amplify uncertainty; treat as directional only."
- Never present Monte Carlo output as a precise forecast — always include the disclaimer below.

---

## Sector & Peer Comparison

For every analysis, compare the stock against 3–5 peers and sector average:

1. Identify 3–5 direct competitors or sector peers
2. Pull: Forward P/E, PEG, revenue growth, gross margin, ROE, EV/EBITDA
3. Score target relative to peers (above/below sector median for each metric)
4. Produce a compact comparison table

---

## Multi-Horizon Recommendations

Provide a separate rating for each horizon (informed by Monte Carlo):

| Horizon | Timeframe | Key Drivers |
|---|---|---|
| 🏃 Swing | 1–3 months | Technicals, momentum, near-term catalyst |
| 📈 Intermediate | 6–18 months | Fundamentals + valuation, earnings trend |
| 🏦 Long-term | 3+ years | Business quality, moat, sector tailwinds |

---

## Catalyst Calendar

Always include:
- Next earnings date and analyst EPS estimate
- Ex-dividend date (if applicable)
- Upcoming conferences, product launches, regulatory decisions
- Analyst day or management guidance updates

---

## Historical Backtesting

Show whether the scoring model would have correctly called this stock at prior snapshots.

### What to fetch

For each period (12mo ago, 24mo ago, 36mo ago):
1. Price at that date (use Yahoo Finance historical or Macrotrends)
2. Key financials at that time (use SEC EDGAR 10-Q/10-K filings for TTM data)
3. Estimate the composite score using the same pillar framework
4. Compare to actual forward return over the subsequent period
5. Note whether the signal (Buy/Hold/Avoid) was correct

### Guardrails

- If historical data is unavailable for a period, mark that row as "N/A — data unavailable"
- Always add: "Backtest uses approximate scores reconstructed from historical filings; hindsight bias may apply"
- Do not cherry-pick periods — always show all three (12/24/36mo) even if unfavorable

---

## Alert & Re-analysis Logic

At the end of every report, generate a personalized Alert Checklist. The user saves this and pastes it back in a future session to trigger re-analysis.

**Workflow instruction:** After outputting the full report, always generate the Alert Checklist block using the actual price target, stop-loss, composite score, and earnings date from the analysis.

---

## Export

At the end of every report, always append the Export Options block.

**If user replies "export markdown":**
Use the Write tool to save the full report to the project root as:
`[TICKER]_analysis_[YYYYMMDD].md`
Confirm the file path after writing.

**If user replies "export pdf":**
Write the markdown file as above, then instruct:
"Open [filename] in a markdown viewer or browser and use File → Print → Save as PDF."

---

## Data Integrity Rules

> **CRITICAL — Never violate these:**
>
> 1. **Never invent numbers.** If unavailable, write `Data unavailable` explicitly.
> 2. **Always cite source + date** for every data point (e.g., "Yahoo Finance, 2026-05-09").
> 3. **If WebFetch fails**, state: "Live data unavailable — using [source/assumption]. Verify before trading."
> 4. **Directional estimates only** when data is missing: "Revenue growth appears positive based on [X], exact figure unavailable."
> 5. **Never make a Buy recommendation** when more than 2 key metrics are missing.
> 6. **Price target guardrail**: No target beyond ±30% from current price without explicit data-backed justification. Flag with ⚠️ if exceeded.
> 7. **Monte Carlo guardrail**: If σ > 60%, flag extreme volatility and note reduced reliability. Never present simulation output as a precise forecast.

---

## Workflow

### Single Stock

1. Ask investor profile + ESG toggle (if not given)
2. Gather data via WebSearch/WebFetch — cite each source and date
3. Score all pillars with bullet rationale
4. Run risk management checks; flag any 🚩 conditions
5. Run Monte Carlo for Intermediate and Long-term horizons
6. Run sector/peer comparison
7. Build multi-horizon recommendations (informed by Monte Carlo)
8. Pull catalyst calendar
9. Fetch historical data for backtesting (12/24/36mo snapshots)
10. Output full report using the template below
11. Append Alert Checklist
12. Append Export Options

### Multi-Stock Comparison

1. Score each stock in parallel with the same profile and weights
2. Run Monte Carlo for each (Intermediate horizon)
3. Build ranking table sorted by composite score
4. Highlight top pick with a "Why this one over the others" paragraph
5. Flag any risk disqualifiers

### Watchlist Ranking

- Score each ticker with condensed analysis (Fundamentals + Valuation only for speed)
- Output ranked table with composite score, rating, one-line thesis, and 🚩 flags
- Top 3 Picks summary at end

---

## Output Template

````
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 STOCK ANALYSIS: [TICKER] — [Company Name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Date: [date]  |  💲 Price: $[price]  |  🏭 Sector: [sector]
🎯 Investor Profile: [profile] [+ ESG if enabled]

## Executive Summary
[3-sentence thesis: what the company does, why the score is what it is,
and the single most important catalyst or risk to watch.]

Composite Score: [score]/100 [emoji] → [Rating]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Pillar Scores
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Pillar | Weight | Score | Key Drivers |
|---|---|---|---|
| 📈 Fundamentals  | [w]% | [0-100] | EPS +X% YoY; FCF yield Y%; D/E Z |
| 📉 Technicals    | [w]% | [0-100] | RSI=X; above/below 50/200MA; RS vs sector |
| 💰 Valuation     | [w]% | [0-100] | Fwd P/E=X; PEG=Y; DCF upside=Z% |
| 🗣 Sentiment     | [w]% | [0-100] | X Buy / Y Hold / Z Sell; short int=N% |
| 🌱 ESG/Quality   | [w]% | [0-100] | [Include only if ESG enabled] |

Composite Score = [formula with values] = [score]/100

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
## 📊 Monte Carlo Price Simulation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Inputs: S₀=$[price]  |  σ=[X]% annualized (ATR=[X]%)  |  μ=[X]%  |  T=[X] days

### Intermediate Horizon (12 months)
Median Target:    $[X]  ([+/-X]%)
10th Percentile:  $[X]  ([+/-X]%)  ← downside scenario
90th Percentile:  $[X]  ([+/-X]%)  ← upside scenario

Probability of +20% gain:         [X]%
Probability of hitting stop-loss:  [X]%
Probability of reaching new ATH:   [X]%

### Long-term Horizon (36 months)
Median Target:    $[X]  ([+/-X]%)
10th Percentile:  $[X]  ([+/-X]%)
90th Percentile:  $[X]  ([+/-X]%)

⚠️ Monte Carlo uses historical volatility and score-derived drift.
   Adjust expectations for major upcoming catalysts. Not a precise forecast.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Sector & Peer Comparison
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Company | Fwd P/E | PEG | Rev Growth | Gross Margin | ROE | EV/EBITDA |
|---|---|---|---|---|---|---|
| **[TICKER]** | | | | | | |
| [Peer 1]     | | | | | | |
| [Peer 2]     | | | | | | |
| [Peer 3]     | | | | | | |
| Sector Avg   | | | | | | |

[1-sentence conclusion: where the stock ranks vs peers and why it matters]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Multi-Horizon Recommendations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Horizon | Rating | Monte Carlo Median | Rationale |
|---|---|---|---|
| 🏃 Swing (1–3 mo)        | [Buy/Hold/Avoid] | N/A | [1 sentence] |
| 📈 Intermediate (6–18 mo) | [Buy/Hold/Avoid] | $[X] ([+/-]%) | [1 sentence] |
| 🏦 Long-term (3+ yr)     | [Buy/Hold/Avoid] | $[X] ([+/-]%) | [1 sentence] |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Catalyst Calendar
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 📣 Next Earnings: [date] (est. EPS: $[X])
- 💵 Ex-Dividend Date: [date or N/A]
- 📅 Upcoming Events: [conferences, launches, regulatory decisions]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 📅 Historical Backtest
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Period | Est. Score | Signal | Price Then | Price Now | Return | vs S&P 500 | Correct? |
|---|---|---|---|---|---|---|---|
| 12 mo ago | [X] | [Signal] | $[X] | $[now] | [+/-X]% | [+/-X]% | [✅/❌/➡️] |
| 24 mo ago | [X] | [Signal] | $[X] | $[now] | [+/-X]% | [+/-X]% | [✅/❌/➡️] |
| 36 mo ago | [X] | [Signal] | $[X] | $[now] | [+/-X]% | [+/-X]% | [✅/❌/➡️] |

Signal accuracy: [X]/3 correct directional calls
⚠️ Approximate scores reconstructed from historical filings. Hindsight bias may apply.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Data Sources
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Yahoo Finance ([date]): price, Forward P/E, beta, ATR
- SEC EDGAR 10-Q ([quarter]): revenue, FCF, D/E
- OpenInsider ([date]): insider transactions
- [Other sources as needed]
[Note any missing data or assumptions]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 📋 Alert Checklist — Save for Re-analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Paste this back in a future session to trigger re-analysis:

[ ] Price reaches $[target] → re-analyze for exit
[ ] Price drops to $[stop]  → review stop-loss decision
[ ] Composite score drops below [threshold-10] → reassess thesis
[ ] Next earnings: [date]   → re-analyze 2 days before
[ ] Review again by: [today + 30 days]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💾 Export Options
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reply with:
  "export markdown" → saves report as [TICKER]_analysis_[YYYYMMDD].md
  "export pdf"      → saves markdown file + instructions to print as PDF
````

---

## Data Sources Reference

| Data Type | Source |
|---|---|
| Financials (income, balance, cash flow) | SEC EDGAR, Macrotrends |
| Live price, ratios, beta, ATR | Yahoo Finance, Finviz |
| Analyst ratings & estimates | Seeking Alpha, Finviz |
| Insider transactions | OpenInsider |
| Short interest | Finviz, Nasdaq short interest |
| News sentiment | CNBC, Reuters, Seeking Alpha headlines |
| Sector/peer comparisons | Finviz screener, Macrotrends |
| Historical prices | Yahoo Finance historical, Macrotrends |
| ESG / moat ratings | Morningstar, MSCI ESG (if accessible) |
