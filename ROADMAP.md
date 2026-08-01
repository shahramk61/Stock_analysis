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
- [x] Quantitative Analyst agent (Phase 1 — standalone data provider; v2 report enhancements with 12+ signals + dynamic conviction)
- [x] Merged to `main`

## Milestone 7 — TradingAgents Integration (Phase 2)
- [x] Port `quantitative_analyst.py` to TradingAgents (`~/TradingAgents`)
- [x] Add `quantitative` to `selected_analysts` + CLI
- [x] Wire into GraphSetup; expose `quantitative_report` to Researchers / Risk team
- [x] Unit tests (`tests/test_quantitative_analyst.py`)
- [x] Full end-to-end run with GPU signals (local smoke test + 7-model ensemble, HMM, GARCH, MC risk etc. exercised via `test_quant_analyst.py`)
  - Note: "live LLM API keys" validation occurs when running full TradingAgents graph with other analyst nodes (separate repo)

## Milestone 8 — Backtesting & Validation (Execution Readiness)

- [x] Historical replay infrastructure (`backtest/` package): `load_historical_data` + `asof_snapshot` for point-in-time slices (strict no look-ahead)
- [x] Signal compatibility: `hist=` / `asof=` support added to 15+ price/vol/liquidity signals in `stock_signals.py` so they replay on historical data
- [x] `calculate_pillars` + Quant Analyst node made replayable (pass-through `hist`/`asof`, `use_gpu_signals` for fast mode, `debate_mode` for conversation stub)
- [x] Real policy on agent outputs: `default_policy` consumes overall score + multi-horizon consensus + `quantitative_conviction` + risk signals → `TradeSignal` (action, risk size, stop, rationale)
- [x] Simulator + metrics: risk-based position entry, basic stops/exits, equity curve, drawdown, vs buy-and-hold benchmark, trade logging
- [x] CLI (`scripts/backtest.py`): `--fast`, `--debate`, `--export`, `--validate`, `--no-forecasts`
- [x] Hard risk filters (high VaR / Bear → flat) + cash-capped `position_size_shares`
- [x] Correct execution: next-open fill, daily stop-on-low, flat exits, BH on window only, no live `info` leak
- [x] No-lookahead / engine unit tests (`tests/test_no_lookahead.py`, `tests/test_backtest_engine.py`)
- [~] Longer 6–12 month validation runs (use `--fast --export`; document results as needed)
- [~] Residual look-ahead: Altman/Piotroski/quality still call live yfinance (need PIT fundamentals later)
- [x] Decision journal + walk-forward memory (stop cooldown, loss streak, Abzu-style gates under `journal/`)

This milestone directly supports the goal of trusting the agent before wiring it to a live broker/agentic API (e.g. Robinhood).

## Milestone 10 — Indicators & Model Performance ✅

- [x] **Risk pillar** actually included in overall score (profile weights)
- [x] Wire **RSI / MACD** into scoring + Quant Analyst + policy
- [x] **Trend pack**: SMA 20/50/200 stack, golden/death flags, **ADX**
- [x] Multi-horizon speed: default horizons `[5,20,50]`, lower NF `max_steps`, LSTM early stop, Chronos pipeline cache
- [x] Score dedupe: one multi-horizon train path for pillar boosts (no triple LSTM/Chronos/ensemble)
- [x] Direction label normalization for policy matching

## Milestone 9 — Future Ideas

| Idea | Effort | Notes |
|---|---|---|
| Document / 10-K knowledge base integration | Medium | Attach earnings transcripts & filings for deeper qualitative analysis |
| Automated watchlist re-scoring on schedule | High | Requires persistent storage or cron-style trigger |
| PDF generation via Pandoc | Low | `pandoc report.md -o report.pdf` if Pandoc installed |
| Options chain analysis | High | IV, put/call ratio, max pain — new pillar or separate skill |
| Dividend growth analysis | Medium | Separate scoring track for income investors |
| Bollinger / vol percentile stretch indicators | Low | Optional after trend pack |
| Full 5-horizon forecasts always on | Low | `full_horizons=True` already supported |
