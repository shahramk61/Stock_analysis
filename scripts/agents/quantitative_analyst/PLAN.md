# Quantitative Analyst Agent - Project Plan

**Project Goal**  
Create a new specialized **Quantitative Analyst** agent for the TradingAgents framework (and potentially standalone use). This agent will leverage our advanced local forecasting and risk models to provide high-quality, model-driven insights that can participate in multi-agent debates.

**Status**: Integration Design Phase Started  
**Last Updated**: 2026-05-16

---

## 1. High-Level Approach

- Develop the new agent **inside the existing `Stock_analysis` repository**.
- Keep it well-organized and importable so it can later be integrated into TradingAgents or contributed back.
- Use our already refactored `signals/` package as the core quantitative engine.
- Output style: **Hybrid** (Natural language summary + structured data/tables).

---

## 2. Recommended Project Structure

```
scripts/
├── agents/
│   └── quantitative_analyst/
│       ├── __init__.py
│       ├── quantitative_analyst.py          # Main agent creation logic
│       ├── tools.py                         # Wrappers / tools for signals
│       └── PLAN.md                          # This tracking document
├── signals/                                 # Existing (refactored)
│   ├── technical.py
│   ├── ml_forecast.py
│   ├── neural_forecast.py
│   └── utils.py
└── signals.py
```

---

## 3. Agent Design

### Agent Identity
- **Name**: `QuantitativeAnalyst`
- **Role**: Advanced Quantitative & Model-Driven Specialist
- **Creator Function**: `create_quantitative_analyst(llm)`

### Core Responsibilities
- Generate multi-horizon forecasts (5d, 10d, 15d, 20d)
- Provide risk metrics (Monte Carlo VaR / CVaR)
- Deliver model consensus and uncertainty estimates
- Participate in Researcher (Bull/Bear) debates with data-backed views

### Output Style (Hybrid)
- Natural language executive summary
- Clear tables for forecasts and risk metrics
- Structured model breakdown
- Final view with conviction level

### Key Functions to Use
From our `signals/` package:
- `get_multi_horizon_forecasts()`
- `get_monte_carlo_risk()`
- `get_rolling_beta()`
- `get_iv_rank_and_skew()`
- `calculate_altman_beneish()`
- `get_earnings_surprise()`

---

## 4. Integration Strategy

**Phase 1 (Current)**: Develop inside `Stock_analysis` repo + create integration design
- Clean, maintainable code
- Easy to test standalone

**Phase 2 (Future)**: Port to TradingAgents as a selectable analyst

---

## 5. Open Questions / Todos

- [ ] Finalize Integration Design
- [ ] Create integration code / instructions
- [x] All core signals added
- [x] Output refined

---

## 6. Progress Log

| Date       | Update                                      | Status |
|------------|---------------------------------------------|--------|
| 2026-05-16 | Created INTEGRATION_DESIGN.md               | Done   |

---

**Next Step**: Review integration design and move to implementation planning.