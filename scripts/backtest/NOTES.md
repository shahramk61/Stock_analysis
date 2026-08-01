# Backtest Implementation Notes & Current Agent Audit (Phase 0)

This file captures the audit of existing decision/risk logic (from plan Phase 0) and implementation notes.

## Audit of Current "Agent" Decision Rules (as of 2026-06)

### Top-level Recommendation Logic
- **Text report** (`scripts/report.py:generate_report`): Strong Buy ≥75, Buy ≥60, else HOLD/SELL.
- **JSON export**: STRONG_BUY ≥75, BUY ≥60, HOLD ≥50, CAUTION ≥35, else SELL (aligned).
- **Dashboard**: similar thresholds; Strong Buy 75+, Buy 60+, Hold/Watch 50+.
- Multi-horizon consensus/trend + quant conviction drive `default_policy` (backtest), not the static rec string alone.
- **Risk filters (strict):** VaR>30 or Bear regime → flat; elevated VaR / bearish MACD+ADX/SMA → size cut.
- **Execution model (corrected):** signal at decision close → **next open fill**; **daily stop on low** (gap → open); **flat exits** next open; size **cash-capped** (≤95% notional); equity marked daily; BH on test window only; live `info` not used in replay.
- Demo / `--relaxed` paths removed.
- **Multi-signal entry (`choose_entry`):** trend (SMA/ADX/MACD), multi-horizon consensus, FinBERT/news, plus classic score/conviction paths; hard VaR>30 / Bear regime / soft-path bearish consensus blocks; memory cooldown still wins.
- **Fast mode:** skips multi-horizon training but keeps FinBERT (`use_gpu_signals=True`) so news leverage can fire without full ensemble cost.

### Role of Multi-Horizon Forecasts
- Rich data in `multi_horizon_forecasts` (or `multi_h`): per-horizon median/avg/static-wgt/dynamic-wgt returns, direction, model_disagreement, num_models, consensus_direction, trend_signal, daily paths + dates + per-model breakdown for 5/10/15/20/50d.
- Heavily featured in reports/dashboards (tables, charts).
- Used indirectly via "Consensus" and "Trend" in human interpretation.
- **Not** a direct input to the simple score-based rec today. Strong candidate for policy in backtester (e.g., require Bullish consensus + positive median for long).

### Quantitative Analyst / Conviction
- `scripts/agents/quantitative_analyst/quantitative_analyst.py`:
  - Produces `quantitative_conviction` (High/Medium/Low) + raw_score (lower = better for risk).
  - `compute_quant_conviction(...)`: tunable points system.
    - Factors: MC VaR (tail), Altman Z (distress), HMM regime (Bear penalty), Piotroski, quality GP/accruals, 6m momentum, IVR, GARCH vol_ratio, vol-price corr.
    - Thresholds: >=6 Low, >=3 Medium, else High.
  - Structured `quantitative_signals` dict (risk, regime, quality, momentum, liquidity_flow incl. IV/OBV/CMF/vol corr/amihud/turnover, beta, earnings, garch, atr, multi_horizon summary).
  - Also Markdown report + optional debate_commentary stub.
- Designed explicitly as **data provider** for downstream (Researchers/Trader/Risk in TradingAgents or similar). Perfect for backtest policy input.
- "Conviction" is meant to help weigh the data.

### Risk Management Elements (Documented vs Implemented)
**Claimed in docs/ROADMAP (Milestone 1/3/5, README, SKILL):**
- Position sizing, ATR-based stop-losses, R/R ratio, 8 auto-flags, alert checklists (price target, stop, score threshold, earnings triggers).

**Actually present in code:**
- **Monte Carlo** (`scripts/montecarlo.py`):
  - `run_monte_carlo(..., stop_loss_pct=0.15)` → stop_price, prob_stop_hit (path mins < stop), prob_negative, p10/p90/median, score-derived drift (SCORE_TO_DRIFT table: 80→+0.30 drift ... 0→-0.12).
  - Used in reports + dashboard (visuals + "Stop-loss level (−15%)").
- **ATR**:
  - `scripts/fetch_data.py:calculate_atr` (14-day on hist) → stored in data as 'atr', 'atr_pct'.
  - `scripts/stock_signals.py:get_atr_volatility_clustering` → atr_percent, current_vol, vol_clustering (High/Low vs 1y), risk_level (Elevated/Normal).
  - Penalty in technicals pillar (`score.py`: -10 if "High" clustering).
- **Other risk signals** (all fed to scoring/quant):
  - `get_monte_carlo_risk` (separate 10k-path VaR/CVaR 95%, simulated_annual_vol, risk_level High/Med/Low based on VaR>30/20).
  - GARCH forecast + vol_ratio (penalty in techs if >1.4; forward vol in quant report).
  - Regime (HMM Bull/Bear/Neutral) → ±8 bonus in techs + conviction.
  - Altman Z (Safe/Grey/Distress) → ESG and conviction.
  - Liquidity (Amihud, turnover, OBV/CMF, vol-price corr) → boosts + conviction.
- **In Quant Analyst report**: Dedicated "Risk & Volatility" section (MC VaR/CVaR/vol, GARCH, ATR clustering) + conviction + Key Takeaways that call out elevated tail risk, Grey Z, etc.
- **No** explicit position sizing formula (e.g. risk% / (ATR or VaR)) or R/R calculator or "8 auto-flags" or alert generation code in current canonical scripts. These appear to be planned / partially described in older roadmap items.

### Other Notes from Audit
- Profile weights are in `score.py` (Balanced etc. for pillars).
- Boosts/penalties in pillars are the "secret sauce" (regime, vol, quality, liquidity, mom, DL/FinBERT).
- JSON is the intended handoff to "trading bots".
- The whole system (esp. post recent Quant Analyst polish) is already quite rich for a backtest policy to consume.

## Implementation Notes
- See approved plan.md (session root) for full phased approach.
- Priority for early phases: make replay safe (as-of data) + minimal engine + policy that reuses the above.
- Keep live behavior 100% unchanged (optional params with defaults).
- Next todos will reference this audit for policy defaults.

(Updated during bt-00 / bt-01)
