# GME one-month pipeline audit (2026-07-01 → 2026-08-02)

**Goal:** Full walk-forward backtest audit of GameStop for ~1 month and forecast help/hurt analysis.  
**Date of audit:** 2026-08-02  
**Scope:** Analysis only (no policy/forecast code changes).

---

## 1. Backtest setup (paired runs)

| Field | Value |
|--------|--------|
| Ticker | GME |
| Window | **2026-07-01 → 2026-08-02** |
| Capital | $100,000 |
| Risk / trade | 1% |
| Rebalance | every **2** trading days |
| Mode | **swing** (next-open fill, daily stop-on-low, flat exits) |
| Memory | on |
| Profile | Balanced |

| Run | CLI | Forecasts | Fast |
|-----|-----|-----------|------|
| A | `python scripts/backtest.py GME --start 2026-07-01 --end 2026-08-02 --rebalance-days 2 --fast --export --journal` | **off** | True |
| B | same without `--fast` | **on** | False |

Artifacts:
- `backtest_decisions_GME.json` (last run = forecasts-on)
- Scratch copies: `{SCRATCH}/backtest_decisions_GME_forecast_{off,on}.json`
- Journals: `journal/runs/GME_2026-07-01_2026-08-02_*.json`
- CLI captures: `{SCRATCH}/gme_forecast_{off,on}.txt`

---

## 2. Results (metrics + decision tally)

### Forecasts **off** (`--fast`)

| Metric | Value |
|--------|--------|
| Final equity | $100,000 (**0.0%**) |
| Buy & hold (window) | **−4.06%** (22.64 → 21.72) |
| vs BH | **+4.06%** (by sitting out) |
| Max drawdown | 0.0% |
| Trades | **0** |
| Decisions | **11** · long=**0** · flat=**11** |
| Avg score | **~56.3** |
| Win rate / expectancy | n/a (no trades) |
| Sample rationale | `Score 57.9, Neutral, Low, trend=Bearish → flat` |

### Forecasts **on** (full multi-horizon ensemble)

| Metric | Value |
|--------|--------|
| Final equity | $100,000 (**0.0%**) |
| BH / vs BH / MaxDD | **same** as off (−4.06% / +4.06% / 0%) |
| Trades | **0** |
| Decisions | **11** · long=**0** · flat=**11** |
| Sample early | `Score 57.8, Neutral, Low, trend=Bearish → flat` |
| Sample late | `Score 54.8, **Bullish**, Low, trend=Mixed → flat` (2026-07-24) |

### Decision log (all flat)

| Date | Score off | Score on | Δ | Off consensus | On consensus (from rationale) | Action |
|------|-----------|----------|---|---------------|-------------------------------|--------|
| 2026-07-01 | 57.9 | 57.8 | −0.1 | Neutral | Neutral | flat |
| 2026-07-06 | 58.7 | 58.6 | −0.1 | Neutral | Neutral | flat |
| 2026-07-08 | 56.3 | 56.8 | +0.5 | Neutral | Neutral | flat |
| 2026-07-10 | 56.9 | 57.0 | +0.1 | Neutral | Neutral | flat |
| 2026-07-14 | 57.0 | 56.9 | −0.1 | Neutral | Neutral | flat |
| 2026-07-16 | 55.9 | 55.7 | −0.2 | Neutral | Neutral | flat |
| 2026-07-20 | 54.1 | 54.0 | −0.1 | Neutral | Neutral | flat |
| 2026-07-22 | 54.7 | 54.6 | −0.1 | Neutral | Neutral | flat |
| 2026-07-24 | 54.7 | 54.8 | +0.1 | Neutral | **Bullish** | flat |
| 2026-07-28 | 56.1 | 55.7 | −0.4 | Neutral | **Bullish** | flat |
| 2026-07-30 | 57.4 | 57.3 | −0.1 | Neutral | **Bullish** | flat |

**Trade exits:** none (no entries). No stop vs session-close comparison applies this month.

---

## 3. Pipeline weak points (evidence-backed)

### W1 — Score / text “BUY” vs policy **flat** (primary agent confusion)

**Evidence (live handoff, end of window):**
- `overall_score` **64.9**, `recommendation` **BUY**
- Pillars: tech **85.6**, valuation **95**, sentiment **95** vs fund **30**, risk **35**
- DCF upside **+201.6%** (intrinsic 65.5 vs 21.72)
- `policy_hint`: **action=flat**, conviction **Low**, risk **0.0%**  
  rationale: `Score 64.9, Neutral, Low, trend=Mixed → flat`
- Multi-turn debate (`decisions/live_GME_*.json`) correctly stayed flat with `policy_conflict=false`, but only after explicit research-vs-execution split.

**Why it hurts:** Report layer and execution layer disagree. Bull agents (and humans) overweight BUY/DCF; risk stack silently zeros size.

### W2 — Hard risk gates: **VaR ≫ 30** + quant **Low** (execution always blocked)

**Backtest month (as-of path audit on 07-01, 07-16, 07-24, 07-30):**
- MC `var_95` **66.8–68.0** every sample day → `high_var=True` (threshold 30)
- Quant conviction **Low** every sample day
- `choose_entry` always **flat** with Low conv (soft paths B/C/D require Medium+)
- Even if Path C proposed long with Medium + Bullish multi-h, `default_policy` hard-filters:  
  `if high_var or regime_bear → flat`

**Live handoff (2026-08-02):** VaR **82.3**, CVaR **87.4**, regime **Bear** (prob 1.0), death_cross **true** — same structural block.

**Month implication:** Zero trades is not “missed alpha from score 56”; it is **by design** under VaR/Low-conviction gates. Sitting out beat BH by 4pp this window, so the block was *correct for risk*, but the stack cannot express a sized long on GME-like names until VaR compresses.

### W3 — Trend stack stays Bearish/Mixed with death cross (no Path B)

As-of samples:
- 07-01 / 07-16: stack **Bearish**, `death_cross=true`, `trend_bear=true`
- 07-24 / 07-30: stack **Mixed**, death_cross still true, not Path B eligible

Path B needs `trend_bull` + Medium/High + not `regime_bear`. Never satisfied this month.

### W4 — Execution / sizing / stops: **no stress test this month**

With 0 trades, stop-on-low, cash-capped sizing, and memory cooldowns never fire. Weak point is **coverage**: GME month only validates the flat path. Prior AAPL session runs are needed for stop quality—not this GME window.

### W5 — Forecast field **internal inconsistency** (confuses agents if exposed)

On 2026-07-01 forecasts-on path audit:
- `horizons_n=3` (models ran)
- `consensus_direction=Neutral`, `h5_dir=Neutral`
- but `mh_trend=Accelerating Bullish`

Late month: consensus flips **Bullish** while score barely moves and 5d direction can remain Neutral. Agents reading “Accelerating Bullish” or “Bullish consensus” without VaR/conviction context will over-weight noise.

---

## 4. Forecast signal audit: help / confuse / no material effect

### What forecasts changed

| Layer | Forecasts off | Forecasts on | Material? |
|-------|---------------|--------------|-----------|
| Score | 54.1–58.7 | within **±0.5** of off | No |
| Policy action | flat ×11 | flat ×11 | No |
| Trades / PnL | 0 / 0% | 0 / 0% | No |
| multi_h horizons | **empty** | **3 horizons** populated | Yes (data only) |
| consensus in rationale | always Neutral | **Bullish** on 07-24, 07-28, 07-30 | Yes (language) |
| Path C taken? | No | **No** (Low conv blocks; VaR would still flat) | No |

### Path C (`choose_entry` multi-horizon leverage)

```text
Path C: overall≥54 AND consensus_bull AND conv∈{High,Medium}
        AND not trend_bear AND not regime_bear
```

- GME late-July had overall ≥54 and (on) consensus Bullish, but **conv=Low** → Path C **never entered**.
- Unit test: `tests/test_gme_forecast_policy_audit.py::test_path_c_blocked_when_conviction_low_even_if_consensus_bullish`
- Even with Medium, `test_high_var_hard_block_flats_path_c_long` shows VaR 67.4 still forces flat.

### Agent-facing handoff (`--fast` default path)

- `prepare_decision_handoff.py ... --fast` → empty horizons, Neutral consensus (same as backtest off).
- Live multi-turn debate used that handoff: agents never saw real multi-h paths; debate was driven by score/DCF vs VaR/Bear.

### Conclusion (pick one)

**Primary: no material effect** on GME month **execution** (identical 0 trades, 0% return).

**Secondary: confuses** multi-agent / research consumers when forecasts-on language (`Bullish` consensus, `Accelerating Bullish` trend_signal) appears alongside score≈55, Low conviction, and VaR~67–82 — without changing `policy_hint.action`.

**Does not help** this month: no improved entry timing, no Path C fills, negligible score lift.

### Recommendation for GME-like names

1. **Default agent handoff:** keep `--fast` / forecasts off for decisions unless VaR & conviction already allow soft paths; otherwise multi-h only adds narrative noise.
2. **If forecasts-on:** surface consensus **only after** hard filters (or label as “research-only, not executable”).
3. **Do not treat** text BUY / DCF upside as trade permission; always pair with `policy_hint` and VaR.
4. **Fix confusion product-side (future work, out of scope):** align report recommendation with policy, or dual-label “Research BUY / Execute FLAT”.

---

## 5. Ranked weak-point list

| Rank | Weak point | Severity (this month) | Evidence |
|------|------------|----------------------|----------|
| 1 | Score/text BUY vs policy flat dual messaging | **High** (agent confusion) | handoff 64.9 BUY + policy flat; live debate |
| 2 | Chronic high VaR + Low quant → structural no-trade | **High** (execution) | var 66–82; 11/11 flat both runs |
| 3 | Soft multi-h Path C dead under Low conv | **Medium** | late Bullish consensus still flat; unit tests |
| 4 | Forecast trend_signal vs consensus mismatch | **Medium** (confuse) | Accelerating Bullish + Neutral consensus |
| 5 | No trade → stop/size untested on GME | **Low** this window | 0 trades |

---

## 6. Forecast recommendation (one line)

**For GME-like high-VaR names: forecasts neither help nor hurt fills this month — default them off for agent decisions; if on, treat multi-h as research-only until conviction/VaR gates open.**

---

## 7. Agent conversation review (multi-turn GME debate)

Full notes: **`decisions/GME_agent_conversation_audit.md`**  
Sources: `debate_GME_20260802T182716Z.json`, `live_GME_20260802T182812Z.json`, `handoff_GME.json`.

### Outcome quality
| Check | Result |
|--------|--------|
| Structure Bull→Bear×2 → Manager → Trader | OK |
| Grounding vs handoff (VaR 82.3, score 64.9, DCF +201.6%, etc.) | OK — no invented core metrics |
| multi_h / FinBERT under `--fast` | Correctly called **Neutral / empty** |
| Final action vs `policy_hint` | **flat / HOLD**, `policy_conflict=false` |
| Bull R2 | Stand-down on capital; research vs execution split |
| Report BUY treated as trade ticket? | **No** (Manager/Trader explicit) |

### Issues found in the conversation
**Hard errors:** none (numbers match handoff; policy respected).

**Process / quality warnings:**
1. **Not real multi-agent** — all 6 turns share timestamp `2026-08-02T18:28:01Z`; single orchestrator batch roleplay, not independent `stock-bull` / `stock-bear` subagent spawns. Reduces adversarial independence.
2. **Cross-ticker leakage** — Bull R2 cites “TSLA-style 36 CAUTION” and “not a −24% below-200 air pocket” (session memory). Not in GME handoff; mild protocol noise (contrast is clear that GME is −4.12% vs SMA200).
3. **System dual-message still the root pain** — agents spent the debate resolving **BUY text vs flat policy**; conversation is healthy *because* it refused to long, but the handoff still confuses readers/agents until labels are dualled.

### Implication for forecast audit
This debate used **forecasts-off handoff** only. Agents never saw late-July multi-h **Bullish** consensus from the forecasts-on backtest. So the conversation does **not** contradict the finding that forecasts-on mainly changes *language* in walk-forward; it shows agents stay disciplined when multi_h is honestly Neutral.

---

## Appendix — verification artifacts

| File | Content |
|------|---------|
| `{SCRATCH}/gme_backtest_summary.txt` | Paired metrics |
| `{SCRATCH}/gme_forecast_off.txt` / `gme_forecast_on.txt` | Full CLI logs |
| `{SCRATCH}/gme_policy_path_audit.json` | As-of policy path table |
| `{SCRATCH}/gme_handoff_forecast_diff.txt` | Handoff + path + rationale diffs |
| `tests/test_gme_forecast_policy_audit.py` | Durable shipped-code tests |
| `decisions/handoff_GME.json` | Agent freeze (forecasts off / fast) |
| `decisions/live_GME_*.json` | Multi-turn decision (flat) |
| `decisions/GME_agent_conversation_audit.md` | Debate transcript review |
