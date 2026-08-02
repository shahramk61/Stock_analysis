# Stock Analysis

Local Python pipeline for **data-driven equity scoring**, **risk policy**, **walk-forward backtests**, and **Grok Build multi-agent decisions**.

| Layer | What runs where |
|--------|------------------|
| **Measurement** | Your machine — `scripts/` (yfinance, scores, VaR, journal) |
| **Decisions** | Grok Build session — Bull/Bear/Manager/Trader (subscription; **no** `XAI_API_KEY`) |

**Canonical code:** `scripts/` only. Do not invent prices, scores, or risk metrics — run the pipeline.

---

## Quick start (new team member)

```bash
git clone https://github.com/shahramk61/Stock_analysis.git
cd Stock_analysis

# Python 3.11+ recommended
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -r requirements.txt

# Optional GPU (PyTorch CUDA) — see comments in requirements.txt
# Optional: open this folder in Grok Build for /decide-stock and project agents
```

**Smoke checks**

```bash
# Unit tests (no market data network for most; some signal tests may download)
python tests/test_recommendation_dual.py
python tests/test_policy_leverage.py
python tests/test_backtest_engine.py
python tests/test_debate_session.py

# One-ticker analysis (needs network for yfinance)
python scripts/analyze.py AAPL --output both --profile Balanced

# Decision handoff (facts only; forecasts OFF by default)
python scripts/prepare_decision_handoff.py AAPL --profile Balanced --fast
```

Full onboarding notes: **[docs/ONBOARDING.md](docs/ONBOARDING.md)** · contributing: **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## Features

- **6-pillar scores** — Fundamentals, Technicals, Valuation, Sentiment, ESG/Quality, **Risk**
- **Profiles** — Balanced, Value, Growth, Momentum
- **Signals** — DCF, Monte Carlo VaR/CVaR, RSI/MACD, SMA/ADX, regime (HMM), GARCH/ATR, liquidity, FinBERT, optional multi-horizon ensembles
- **Dual recommendations** — **Research** (score bands) vs **Execute** (`policy_hint`); Research BUY is **not** a trade ticket
- **Policy** — hard VaR / Bear regime filters, trend leverage, memory cooldowns; multi-horizon Path C **opt-in only**
- **Backtester** — walk-forward, next-open fill, stop-on-low, flat exits, optional **session** (same-day open→close)
- **Journal** — episodic runs + Abzu-style rules under `journal/`
- **Grok multi-turn debate** — Bull ↔ Bear rounds → Manager → Trader (`/decide-stock`)
- **Streamlit dashboard** — `streamlit run scripts/dashboard.py`

---

## Defaults that matter (read this)

| Setting | Default | Opt-in flag |
|---------|---------|-------------|
| Neural multi-horizon forecasts | **OFF** | `--forecasts` |
| Path C multi-horizon **entry** leverage | **OFF** | `--multi-horizon-entry` |
| Decision memory (stop cooldown / loss streak) | **ON** | `--no-memory` to disable |
| Fast handoff/backtest | FinBERT may still run; skips full ensemble retrain | `--fast` |

Why: a GME feature audit showed forecasts did not improve fills and could confuse agents with Bullish language under a flat policy. Keep models for research; do not treat them as the trade driver unless you opt in and calibrate.

**Always prefer Execute / `policy_hint` over text BUY** when they disagree (`policy_conflict`).

---

## Common commands

### Analysis

```bash
python scripts/analyze.py AAPL --output both --profile Balanced
python scripts/analyze.py MSFT --output json --profile Growth
streamlit run scripts/dashboard.py
```

### Decision handoff + multi-agent (Grok Build)

```bash
# 1) Freeze pipeline facts (local)
python scripts/prepare_decision_handoff.py TSLA --profile Balanced --fast

# 2) In Grok Build chat (this repo open)
/decide-stock TSLA
# optional: /decide-stock GME --rounds 2
```

Helpers:

```bash
python scripts/debate_session.py init AAPL --rounds 2 --handoff decisions/handoff_AAPL.json
python scripts/debate_session.py status decisions/debate_AAPL_*.json
```

### Backtest

```bash
# Swing (default): signal at close → next open; stop on low; flat next open
python scripts/backtest.py AAPL --start 2026-07-01 --end 2026-08-02 --fast --export --journal

# Session mode: same-day open → close (daily bars)
python scripts/backtest.py AAPL --session --rebalance-days 1 --fast --export

# Opt-in forecasts / Path C (slow; research)
python scripts/backtest.py GME --start 2026-07-01 --end 2026-08-02 --forecasts --export
python scripts/backtest.py GME --start 2026-07-01 --end 2026-08-02 --forecasts --multi-horizon-entry --export
```

### Tests

```bash
python tests/test_recommendation_dual.py
python tests/test_policy_leverage.py
python tests/test_gme_forecast_policy_audit.py
python tests/test_backtest_engine.py
python tests/test_debate_session.py
python tests/test_decision_memory.py
python tests/test_no_lookahead.py
python tests/test_quant_schema.py
# Optional GPU quant smoke:
python test_quant_analyst.py
```

---

## Architecture (mental model)

```
yfinance / signals  →  score.calculate_pillars  →  quant conviction
                              ↓
                    default_policy (Execute)
                              ↓
              Research label (score)  |  policy_hint (trade intent)
                              ↓
         handoff JSON  →  Grok Bull/Bear/Manager/Trader  →  live decision
                              ↓
              backtest engine (walk-forward replay of same policy)
```

| Path | Role |
|------|------|
| `scripts/stock_signals.py` | Quantitative signals |
| `scripts/score.py` | Pillars + overall score |
| `scripts/recommendation.py` | Dual Research / Execute labels |
| `scripts/backtest/policy.py` | `default_policy`, `choose_entry` |
| `scripts/backtest/engine.py` | Walk-forward execution |
| `scripts/prepare_decision_handoff.py` | Frozen facts for agents |
| `scripts/agents/` | Quant node, debate helpers, schemas, PROMPTS |
| `.grok/` | Grok skills, commands, agent cards |

---

## Scoring (Research labels)

| Pillar | Balanced | Value | Growth | Momentum |
|--------|----------|-------|--------|----------|
| Fundamentals | 25% | 20% | 30% | 15% |
| Technicals | 20% | 15% | 25% | 30% |
| Valuation | 20% | 30% | 15% | 15% |
| Sentiment | 10% | 10% | 10% | 15% |
| ESG | 10% | 10% | 5% | 10% |
| Risk | 15% | 15% | 15% | 15% |

| Score | Research label |
|-------|----------------|
| 75–100 | STRONG_BUY |
| 60–74 | BUY |
| 50–59 | HOLD |
| 35–49 | CAUTION |
| 0–34 | SELL |

Execute still applies VaR, Bear regime, conviction, and memory. Example dual line:

`Research BUY | Execute FLAT`

---

## Project structure

```
Stock_analysis/
├── scripts/                 # Canonical pipeline (edit here)
│   ├── analyze.py, score.py, report.py, recommendation.py
│   ├── backtest.py, backtest/{engine,policy,data,memory,metrics}.py
│   ├── prepare_decision_handoff.py, debate_session.py
│   ├── dashboard.py, fetch_data.py, montecarlo.py, dcf.py
│   └── agents/              # Quant + debate schema + PROMPTS.md
├── tests/                   # Unit / policy / backtest tests
├── decisions/               # Handoffs, debates, audits (many gitignored)
├── journal/                 # Memory rules + run dumps (runs/*.json ignored)
├── docs/                    # ONBOARDING, grok-hooks
├── .grok/                   # Grok Build skills, commands, agents
├── requirements.txt
├── CONTRIBUTING.md
└── README.md
```

Generated locally (usually **not** committed): `signals_*.json`, `backtest_decisions_*.json`, `lightning_logs/`, `decisions/handoff_*.json`, `decisions/live_*.json`, `journal/runs/*.json`.

---

## Grok Build usage

| Command / skill | Purpose |
|-----------------|---------|
| `/analyze-stock TICKER` | Pipeline-backed analysis |
| `/watchlist …` | Rank tickers |
| `/decide-stock TICKER` | Multi-turn debate + final proposal |
| `.grok/agents/stock-*.md` | Bull, Bear, Manager, Trader, Quant reader |

See [docs/grok-hooks.md](docs/grok-hooks.md). Primary path does **not** use the public xAI HTTP API.

---

## Roadmap & license

- Product plan: [ROADMAP.md](ROADMAP.md)  
- Journal rules: [journal/README.md](journal/README.md)  
- License: **MIT** — [LICENSE](LICENSE)

---

## Disclaimer

This repository is for **research and education**. It is not investment advice. No live broker orders ship with the default stack. Past backtests do not guarantee future results. Always re-run the pipeline for current numbers.
