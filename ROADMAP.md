# Stock Analysis Skill — Roadmap

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Done

---

## Milestone 1 — Core Skill ✅
- [x] 4-pillar weighted scoring model (Fundamentals, Technicals, Valuation, Sentiment)
- [x] 5 investor profiles with configurable weights
- [x] Risk management (position sizing, stop-loss, R/R ratio, 8 auto-flags)
- [x] Sector & peer comparison table
- [x] Multi-horizon recommendations (Swing / Intermediate / Long-term)
- [x] Catalyst calendar
- [x] Data integrity guardrails (no invented numbers, source citations, price target ±30% cap)
- [x] `/analyze-stock` command (single + multi-stock)
- [x] `/watchlist` command

## Milestone 2 — Polish & Fixes ✅
- [x] YAML frontmatter errors fixed in both command files
- [x] Visual output template with emojis and section separators
- [x] Executive summary at top of every report
- [x] PEG ratio, Forward P/E, Relative Strength vs sector, ATR%, short interest, news sentiment
- [x] MIT LICENSE
- [x] Comprehensive README on main branch

## Milestone 3 — Advanced Features ✅
- [x] Export (Markdown / PDF)
- [x] Monte Carlo Simulation (log-normal GBM → upgraded to true 10,000-path numpy simulation in v4.0)
- [x] ESG / Quality Pillar (toggleable)
- [x] Alert & Re-analysis Logic
- [x] Historical Backtesting

## Milestone 4 — v4.1 Advanced Local Signals ✅
- [x] **Signal 1:** IVR + Options Skew (Volatility Edge) — blended into Technicals pillar at 20%
- [x] **Signal 2:** Altman Z-Score + Beneish M-Score — Financial Health section; Z-Score in ESG pillar
- [x] **Signal 3:** 3-Stage DCF with WACC + 5×5 sensitivity table — blended into Valuation pillar
- [x] **Signal 4:** Earnings surprise history (8 qtrs) + 5-day post-earnings drift — blended into Sentiment
- [x] **Signal 5:** Rolling beta decomposition (market β, sector β, alpha, R², idio vol) — alpha ±5 pts to Technicals

## Milestone 5 — Future Ideas
- [x] **Export (Markdown / PDF)** — "export markdown" / "export pdf" triggers at end of every report
- [x] **Monte Carlo Simulation** — log-normal GBM, median/10th/90th percentile, probability outputs for Intermediate and Long-term horizons
- [x] **ESG / Quality Pillar** — toggleable 5th pillar (moat, governance, Piotroski F-Score, ROIC, controversies) with weight redistribution per profile
- [x] **Alert & Re-analysis Logic** — personalized Alert Checklist appended to every report with price target, stop-loss, score threshold, and earnings date triggers
- [x] **Historical Backtesting** — 12/24/36-month score reconstruction with forward return vs S&P 500 and signal accuracy

---

## Milestone 6 — v5.0 Pipeline & Quant Analyst ✅
- [x] Unified canonical code under `scripts/` (`stock_signals.py`, score, report, dashboard)
- [x] Skill shims re-export from `scripts/` via `_canonical.py`
- [x] Structured JSON output for trading-bot integration
- [x] Quantitative Analyst agent (Phase 1 — standalone data provider)
- [x] Merged to `main`

## Milestone 7 — TradingAgents Integration (Phase 2)
- [ ] Port `quantitative_analyst.py` to TradingAgents
- [ ] Add `quantitative` to `selected_analysts`
- [ ] Wire into GraphSetup; expose `quantitative_report` to Researchers / Trader
- [ ] End-to-end integration test

## Milestone 8 — Future Ideas

| Idea | Effort | Notes |
|---|---|---|
| Claude Project integration (upload 10-Ks) | Medium | Upload earnings transcripts as knowledge base for deeper analysis |
| Automated watchlist re-scoring on schedule | High | Requires persistent storage or cron-style trigger |
| PDF generation via Pandoc | Low | `pandoc report.md -o report.pdf` if Pandoc installed |
| Options chain analysis | High | IV, put/call ratio, max pain — new pillar or separate skill |
| Dividend growth analysis | Medium | Separate scoring track for income investors |
| Quant Analyst v2 debate participation | Medium | Optional speaking role in researcher debate |
