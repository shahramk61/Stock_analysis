# Stock Analysis Skill — Roadmap

Work through these in order. Each item has a clear scope, effort estimate, and definition of done.

---

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Done

---

## Milestone 3 — Advanced Features

### 1. Monte Carlo Price Simulation ⭐ (Do First)
**Effort:** Medium | **Impact:** High

Add probabilistic price targets using geometric Brownian motion instead of single-point estimates.

**Inputs:**
- Current price (S)
- Annualized volatility σ (derived from ATR: σ = ATR/price × √252)
- Expected annual drift μ (derived from composite score: map 0–100 → -20% to +40%)
- Time horizon T in years

**Formula per path (daily steps):**
```
S(t+1) = S(t) × exp((μ - σ²/2) × dt + σ × √dt × Z)
where Z ~ N(0,1), dt = 1/252
```

**Output to add after Risk Management section in report:**
```
📊 Monte Carlo Simulation (10,000 paths) — [Horizon]
──────────────────────────────────────────
Median Target:    $[X]  ([+/-]%)
10th Percentile:  $[X]  ([+/-]%)  ← downside scenario
90th Percentile:  $[X]  ([+/-]%)  ← upside scenario

Probability of +20% gain:        [X]%
Probability of hitting stop-loss: [X]%
Probability of reaching new ATH:  [X]%
──────────────────────────────────────────
⚠️ Simulation uses historical vol. Adjust for upcoming catalysts manually.
```

**Implementation note:** Claude performs the calculation directly using the
GBM formula above — no external tools needed for the rule-of-thumb version.
For full simulation accuracy, optionally allow Bash + Python.

**Definition of done:**
- [ ] Monte Carlo section added to SKILL.md after Risk Management
- [ ] Output template updated with simulation block
- [ ] Score-to-drift mapping table defined (e.g. score 80 → +25% drift)
- [ ] Guardrail: flag if σ > 60% (extreme vol, simulation less reliable)

---

### 2. ESG / Quality Pillar (Optional, Toggleable)
**Effort:** Medium | **Impact:** Medium-High

Add a 5th scoring pillar that users can opt into. When enabled, redistribute 5–10% from other pillars.

**Metrics to score:**
| Metric | Source |
|---|---|
| Economic Moat (Wide/Narrow/None) | Morningstar, analyst reports |
| Governance (insider ownership, board independence) | SEC proxy filings |
| Piotroski F-Score (0–9) | Derived from financial statements |
| ROIC trend (improving/stable/declining) | Financial statements |
| ESG controversies / environmental flags | News, MSCI ESG ratings |

**Weight redistribution when ESG enabled (Balanced example):**
- Fundamentals: 30% (−5%)
- Technicals: 22% (−3%)
- Valuation: 23% (−2%)
- Sentiment: 15% (0%)
- ESG/Quality: 10% (new)

**Definition of done:**
- [ ] ESG pillar metrics and scoring rubric added to SKILL.md
- [ ] Profile table updated with ESG toggle option
- [ ] Weight redistribution logic documented for each profile
- [ ] Output template includes optional ESG row in pillar table

---

### 3. Historical Score Backtesting
**Effort:** High | **Impact:** High (credibility)

Show whether the scoring model would have correctly called this stock 12, 24, and 36 months ago.

**What to fetch and show:**
- Price 12/24/36 months ago
- Estimated score at that time (based on then-current financials — use TTM data from filings)
- Actual forward return vs S&P 500 over same period
- Whether a "Buy" signal at that time would have been profitable

**Output block:**
```
📅 Backtest Snapshot
──────────────────────────────────────────
Period       Score  Signal  Actual Return  vs S&P 500
12 mo ago    72     Buy     +31%           +18% ✅
24 mo ago    58     Hold    +12%           +14% ➡️
36 mo ago    41     Caution -8%            +22% ✅ (avoided drawdown)
──────────────────────────────────────────
Historical signal accuracy: 3/3 correct directional calls
```

**Data sources:** SEC EDGAR historical filings, Macrotrends for historical price/ratios.

**Definition of done:**
- [ ] Backtest workflow added to SKILL.md
- [ ] Output template includes backtest block
- [ ] Guardrail: if historical data unavailable for a period, mark as "N/A — data unavailable"
- [ ] Caveat note: "Backtest uses approximate scores; hindsight bias may apply"

---

### 4. Alert & Re-analysis Logic
**Effort:** Low-Medium | **Impact:** Medium

Let users set trigger conditions; Claude stores them as a checklist to revisit.

**Supported triggers:**
- Score drops below a threshold (e.g. "re-analyze if score < 60")
- Price hits target or stop-loss
- Next earnings date arrives
- Specific time interval (e.g. "remind me in 30 days")

**Implementation:** At end of every report, Claude outputs a structured
"Alert Checklist" block. User can paste it back in a future session to trigger re-analysis.

**Output block to add at end of report:**
```
📋 Alert Checklist — Save this for re-analysis triggers
──────────────────────────────────────────
[ ] Price reaches $[target] → re-analyze for exit
[ ] Price drops to $[stop]  → review stop-loss
[ ] Score drops below [threshold] → reassess thesis
[ ] Next earnings: [date]   → re-analyze 2 days before
[ ] Review again by: [date + 30 days]
```

**Definition of done:**
- [ ] Alert Checklist block added to output template in SKILL.md
- [ ] Workflow instruction: "at end of report, always generate alert checklist"
- [ ] Add `/watchlist` note: "paste saved checklists to trigger batch re-analysis"

---

### 5. One-Click Export (Markdown / PDF)
**Effort:** Low | **Impact:** Medium

At the end of every report, offer export options.

**Output to append to every report:**
```
──────────────────────────────────────────
💾 Export Options
Reply with:
  "export markdown" → save clean report as TICKER_YYYYMMDD.md
  "export pdf"      → formatted version ready to print/share
──────────────────────────────────────────
```

**For "export markdown":** Write the report to a file in the project root
using the Write tool: `TICKER_analysis_YYYYMMDD.md`

**For "export pdf":** Generate the markdown file, then instruct the user to
open it and use browser print → Save as PDF (Claude cannot generate PDFs
directly without a tool).

**Definition of done:**
- [ ] Export block added to output template in SKILL.md
- [ ] Export workflow added: "if user says export markdown, use Write tool to save report"
- [ ] File naming convention documented: `[TICKER]_analysis_[YYYYMMDD].md`

---

## Implementation Order

| # | Feature | Effort | Sessions Est. |
|---|---|---|---|
| 1 | Monte Carlo Simulation | Medium | 1 |
| 2 | ESG / Quality Pillar | Medium | 1 |
| 3 | Backtesting | High | 2 |
| 4 | Alert Logic | Low | 1 |
| 5 | Export | Low | < 1 |

Start with **#5 Export** (quickest win, unblocks testing), then **#1 Monte Carlo** (highest impact).
