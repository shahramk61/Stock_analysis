---
name: stock-analysis
description: >
  Analyze one or more stocks with weighted 6-pillar scoring, quantitative
  signals, risk metrics, multi-horizon forecasts, and optional backtests.
  Use for /analyze-stock, watchlist ranking, ticker deep-dives, or agent policy validation.
---

# Stock Analysis (project skill)

**Owner project:** this repo. Canonical Python lives in `scripts/`.  
**Agent prompts:** `scripts/agents/PROMPTS.md`  
**Quant schema:** `scripts/agents/quantitative_analyst/schemas.py`

## When to use

- User names a ticker or watchlist
- User asks for score, buy/hold view, DCF, risk, or quant report
- User wants a backtest of the scoring/quant agent

## How to run (always prefer real code)

```bash
# Single-name analysis
python scripts/analyze.py TICKER --profile Balanced --output both

# Fast backtest (strict execution: next-open fill, daily stops, flat exits)
python scripts/backtest.py TICKER --start 2024-01-01 --fast --export --validate

# No neural forecasts (regime / risk / technicals only)
python scripts/backtest.py TICKER --start 2024-06-01 --fast --no-forecasts --export

# Quant smoke + schema/golden tests
python test_quant_analyst.py
python tests/test_quant_schema.py
python tests/test_no_lookahead.py
python tests/test_backtest_engine.py
```

Profiles: `Balanced` | `Growth` | `Value` | `Momentum`.

## Output rules (hard)

1. **Never invent** prices, fundamentals, scores, VaR, regime, or recommendations.
2. Run the real pipeline; cite only stdout / `signals_TICKER.json` / quant structured fields.
3. If data is missing, say **unknown / not provided** — do not guess.
4. Map overall score to: Strong Buy ≥75, Buy ≥60, Hold ≥50, Caution ≥35, else Avoid/Sell.
5. **Always surface risk** when present: high MC VaR, Bear HMM regime, distress/Grey Altman Z — even on constructive views.
6. Quant **conviction** language is only **High | Medium | Low** (from `compute_quant_conviction`).
7. Multi-ticker: rank by overall score; Top 3 + risk disqualifiers.
8. Role boundary: Quant Analyst is a **data provider**, not a bull/bear researcher and not a free-form trader.

## Prompt failure modes (fine-tune checklist)

| Failure | What to do |
|---------|------------|
| Number inventing | Stop; re-run `analyze.py` / quant node |
| Role drift | Re-read Quant system card in `PROMPTS.md` |
| Weak risk surfacing | Quote VaR / regime / Z from signals |
| Soft conviction ("very bullish") | Replace with High/Medium/Low only |
| Format drift | Require `quantitative_signals.schema_valid` |
| Debate invents facts | Use template debate; LLM rephrase must pass number check |

## Structured handoff keys (Quant)

Downstream policy and agents must read **fields**, not prose:

- `quantitative_conviction`
- `quantitative_signals.risk.var_95`
- `quantitative_signals.regime.regime`
- `quantitative_signals.multi_horizon.consensus_direction`
- `quantitative_signals.classic` / `trend` / `adx`
- `quantitative_debate_commentary` (facts-only; optional)

Schema version and validation flags: `schema_version`, `schema_valid`, `schema_errors`.

## Useful entry points

| Task | Entry |
|---|---|
| Full report | `scripts/analyze.py` |
| Quant agent | `scripts/agents/quantitative_analyst/` |
| Role prompts | `scripts/agents/PROMPTS.md` |
| Backtest | `scripts/backtest.py` |
| Dashboard | `streamlit run scripts/dashboard.py` |

## Grok decision path

For Grok-authored decisions (not just analysis), use skill **stock-decision** / `/decide-stock`:

```bash
python scripts/prepare_decision_handoff.py TICKER --fast
# then /decide-stock TICKER in Grok Build
```

See root `README.md`, `docs/grok-hooks.md`, and `ROADMAP.md`.
