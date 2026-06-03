# Quantitative Analyst Agent - Project Plan

**Project Goal**  
Create a specialized **Quantitative Analyst** agent for the TradingAgents framework (and standalone use). It leverages local forecasting and risk models for model-driven insights.

**v1 Role**: Data Provider (quantitative reports and risk signals).  
**v2+ Potential**: Light debate participation (optional).

**Status**: Phase 1 complete — standalone agent implemented; signals pipeline unified under `scripts/`.  
**Last Updated**: 2026-06-03

---

## 1. Canonical Pipeline Layout

All analysis code lives under `scripts/` (single source of truth):

```
scripts/
├── stock_signals.py      # Full signals implementation (7-model ensemble, etc.)
├── signals.py            # Public re-export API
├── score.py, report.py, fetch_data.py, montecarlo.py, dcf.py, gpu_utils.py
├── analyze.py, dashboard.py
├── _pipeline.py          # Shared sys.path setup
└── agents/
    └── quantitative_analyst/
        ├── quantitative_analyst.py
        ├── PLAN.md
        ├── INTEGRATION_DESIGN.md
        └── PHASE2_IMPLEMENTATION_PLAN.md
```

`.claude/skills/stock-analysis/scripts/` contains thin shims that re-export from `scripts/` via `_canonical.py`.

---

## 2. Agent Design

| Item | Detail |
|------|--------|
| **Name** | `QuantitativeAnalyst` |
| **Creator** | `create_quantitative_analyst(llm=None)` |
| **Output key** | `quantitative_report` |
| **Signals used** | Multi-horizon forecasts, Monte Carlo VaR/CVaR, beta, IV rank/skew, Altman Z, earnings surprise |

**v1**: Data provider only — no active debate participation.

---

## 3. Phase Status

| Phase | Scope | Status |
|-------|--------|--------|
| **Phase 1** | Agent in `Stock_analysis`, wired to canonical `signals` | Done |
| **Phase 2** | Port to TradingAgents graph (`selected_analysts` includes `quantitative`) | Planned |

See `INTEGRATION_DESIGN.md` and `PHASE2_IMPLEMENTATION_PLAN.md` for Phase 2 steps.

---

## 4. Completed Todos

- [x] Output schema (Markdown + tables + conviction + key takeaways)
- [x] Direct function calls (no LangChain tools in v1)
- [x] `quantitative_analyst.py` implementation
- [x] Test harness: `test_quant_analyst.py`
- [x] Unify signals pipeline (`stock_signals.py` canonical)

---

## 5. Open Todos (Phase 2)

- [ ] Port agent to `tradingagents/agents/analysts/quantitative_analyst.py`
- [ ] Register in GraphSetup / `selected_analysts`
- [ ] End-to-end test inside TradingAgents

---

## 6. Progress Log

| Date | Update | Status |
|------|--------|--------|
| 2026-05-16 | Design docs + agent skeleton | In progress |
| 2026-05-16 | Full signal integration + polish | Done |
| 2026-06-03 | Unified canonical `scripts/` pipeline; updated PLAN | Done |

---

**Next step**: Phase 2 — integrate into TradingAgents per `PHASE2_IMPLEMENTATION_PLAN.md`.