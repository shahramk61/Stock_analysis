# Onboarding — Stock Analysis

Welcome. This doc gets a new contributor from **clone → first green test → first analysis** without tribal knowledge.

## Prerequisites

- **Git**
- **Python 3.11 or 3.12** (3.12 is used in development)
- Optional: **NVIDIA GPU + CUDA** for FinBERT / neuralforecast (CPU works; slower; some models degrade)
- Optional: **Grok Build** IDE/session with this repo open for multi-agent `/decide-stock`

No `XAI_API_KEY` is required for the primary path.

## Setup

```bash
git clone https://github.com/shahramk61/Stock_analysis.git
cd Stock_analysis
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

### GPU torch (optional)

`requirements.txt` pins a generic `torch`. For CUDA, install the wheel that matches your driver, e.g.:

```bash
# Example only — pick the CUDA index for your machine from pytorch.org
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

### First verification

```bash
python tests/test_recommendation_dual.py
python tests/test_policy_leverage.py
python tests/test_backtest_engine.py
```

If those pass, your Python path and policy stack are healthy.

## Mental model (5 minutes)

1. **`scripts/` is source of truth** for numbers.
2. **Research label** = overall score bands (BUY/HOLD/…). Cosmetic for ranking.
3. **Execute / `policy_hint`** = what the backtester and agents should size from (VaR, regime, conviction, memory).
4. **Forecasts are off by default.** Multi-horizon models are research/opt-in (`--forecasts`). Path C entry leverage is separately opt-in (`--multi-horizon-entry`).
5. **Grok agents must not invent metrics.** Always `prepare_decision_handoff.py` first for decisions.

## Day-one exercises

### A. Analyze a liquid ticker

```bash
python scripts/analyze.py AAPL --output both --profile Balanced
# Inspect signals_AAPL.json (gitignored) and console report
```

### B. Freeze a decision handoff

```bash
python scripts/prepare_decision_handoff.py AAPL --profile Balanced --fast
# Read decisions/handoff_AAPL.json — note dual_recommendation + policy_hint
```

### C. Mini backtest

```bash
python scripts/backtest.py AAPL --start 2026-06-30 --end 2026-07-31 --fast --export --journal
# Read backtest_decisions_AAPL.json (gitignored) summary trades / decisions
```

### D. (Optional) Grok multi-turn decision

In Grok Build with this repo:

```
/decide-stock AAPL
```

## Where to change what

| Goal | Start here |
|------|------------|
| New signal | `scripts/stock_signals.py` + wire in `score.py` |
| Entry / risk policy | `scripts/backtest/policy.py` |
| Fill / stop / session execution | `scripts/backtest/engine.py` |
| Dual labels | `scripts/recommendation.py` |
| Agent role text | `scripts/agents/PROMPTS.md`, `.grok/agents/` |
| Handoff shape | `scripts/prepare_decision_handoff.py`, `agents/decision_schema.py` |
| Tests for your change | `tests/` — prefer pure unit tests of shipped functions |

## Branch / PR hygiene

See [CONTRIBUTING.md](../CONTRIBUTING.md).

- Prefer small PRs with tests for policy/scoring changes.
- Do not commit `lightning_logs/`, `signals_*.json`, large journal runs, or live handoffs.
- Do not commit secrets (none are required for the default path).

## Known sharp edges

| Issue | Mitigation |
|-------|------------|
| Report says BUY, policy says flat | Trust **Execute** / `policy_hint`; dual labels surface conflict |
| Forecasts slow / noisy | Leave `--forecasts` off unless you are researching ensembles |
| HMM / neuralforecast warnings | Common; check outputs still finite |
| yfinance MultiIndex quirks | Handled in `backtest/data.py` flatteners |
| Live PE/ROE in `info` | Disabled in backtest replay (`fundamentals_pit` false; empty info) |

## Docs map

| Doc | Content |
|-----|---------|
| [README.md](../README.md) | Overview + commands |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | PR / test expectations |
| [ROADMAP.md](../ROADMAP.md) | Milestones |
| [journal/README.md](../journal/README.md) | Decision memory rules |
| [docs/grok-hooks.md](grok-hooks.md) | Grok automation notes |
| [scripts/backtest/NOTES.md](../scripts/backtest/NOTES.md) | Backtest audit notes |
| [scripts/agents/PROMPTS.md](../scripts/agents/PROMPTS.md) | Multi-agent role cards |
| `decisions/GME_month_audit.md` (if present) | Example feature/forecast audit |

## Getting help

1. Re-run the failing command with the same flags and capture stderr.
2. Check whether the failure is **data** (network/yfinance), **deps** (torch/CUDA), or **logic** (policy assertion).
3. Open an issue/PR with: ticker, command line, Python version, and whether GPU was used.

Welcome aboard.
