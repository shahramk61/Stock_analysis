---
name: stock-analysis
description: >
  Analyze stocks with a 6-pillar weighted score, quantitative signals,
  Monte Carlo risk, optional multi-horizon forecasts, Quantitative Analyst
  reports, dual Research/Execute labels, and walk-forward backtests. Use when
  the user asks to analyze a ticker, rank a watchlist, decide-stock, or backtest.
---

# Stock Analysis Skill v5.1

**Canonical code:** `scripts/` (never invent numbers — run the pipeline).

## Commands

```bash
# Full analysis
python scripts/analyze.py TICKER --profile [Balanced|Growth|Value|Momentum] --output [report|json|both]

# Dashboard
streamlit run scripts/dashboard.py

# Decision handoff (forecasts OFF by default)
python scripts/prepare_decision_handoff.py TICKER --profile Balanced --fast

# Backtest (forecasts OFF by default; Path C multi-h entry OFF)
python scripts/backtest.py TICKER --start YYYY-MM-DD --fast --export
# Opt-in research: --forecasts   Path C: --multi-horizon-entry   Session: --session

# Quant smoke
python test_quant_analyst.py
```

## Dual labels

| Label | Meaning |
|-------|---------|
| **Research** | Score bands (STRONG_BUY / BUY / HOLD / CAUTION / SELL) |
| **Execute** | `policy_hint.action` (long / flat / short) after VaR, regime, conviction, memory |

Never treat Research BUY as a trade when Execute is FLAT (`policy_conflict`).

## Profiles & scoring

Pillars: Fundamentals, Technicals, Valuation, Sentiment, ESG, Risk (0–100 overall).

| Score | Research rating |
|---|---|
| 75–100 | Strong Buy |
| 60–74 | Buy |
| 50–59 | Hold/Watch |
| 35–49 | Caution |
| 0–34 | Avoid / Sell |

## Agent workflow

1. Confirm ticker(s) and optional profile (default **Balanced**).
2. Prefer `python scripts/analyze.py …` or `prepare_decision_handoff.py` for live numbers.
3. For decisions: handoff → multi-turn Bull/Bear → Manager → Trader (`/decide-stock`).
4. Cite real pipeline outputs only.
5. Backtests: `scripts/backtest.py` with `--fast` for routine work.
6. Role cards: `scripts/agents/PROMPTS.md`. Schema: `scripts/agents/decision_schema.py`.

## Integrity failure modes

| Failure | Response |
|---------|----------|
| Number inventing | Refuse; re-run pipeline |
| Role drift (quant as bull/trader) | Quant = data provider only |
| Weak risk surfacing | Always quote elevated VaR / Bear / distress Z |
| Soft conviction language | Only High / Medium / Low |
| Research BUY as order | Use Execute / policy_hint only |

## Key modules

| Path | Role |
|---|---|
| `scripts/stock_signals.py` | Quantitative signals |
| `scripts/score.py` | Pillar scoring (`use_forecasts` default False) |
| `scripts/recommendation.py` | Dual Research / Execute labels |
| `scripts/report.py` | Human + JSON reports |
| `scripts/backtest/policy.py` | Entry policy (Path C opt-in) |
| `scripts/backtest/` | Walk-forward engine |
| `scripts/agents/quantitative_analyst/` | Quant Analyst node |
| `.grok/` | Grok skills, commands, agents |

## Requirements

See `requirements.txt`. Onboarding: `docs/ONBOARDING.md`.

## Version notes (v5.1)

- Dual Research / Execute labels; handoff surfaces `policy_conflict`
- Multi-horizon forecasts + Path C entry **opt-in** (default off)
- Session backtest mode; multi-turn debate transcript helper
- Grok Build subscription path for decisions (no XAI_API_KEY required)
