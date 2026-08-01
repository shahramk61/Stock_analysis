# Grok Build hooks (future automation)

This project’s **decision backend is Grok Build**. Hooks are **opt-in** and not installed by default.

## Today

| Trigger | How |
|---------|-----|
| Manual | `/decide-stock TICKER` in Grok Build |
| Facts only | `python scripts/prepare_decision_handoff.py TICKER` |
| API rephrase | `XAI_API_KEY` + `--grok-debate` on handoff (optional) |

## Later (hook design)

Intended automation (do not enable globally without user consent):

1. **Scheduled watchlist** — cron or Grok scheduled task runs handoff + decide for a list of tickers.
2. **SessionStart (opt-in)** — only if a project flag file exists (e.g. `.grok/auto-decide.watchlist`).
3. **Post-backtest** — after `scripts/backtest.py --export`, offer `/decide-stock` using last blotter + memory.

### Stub entrypoint

```bash
# Does not place trades. Prints / runs prepare path.
./scripts/hooks/run_decide_stock.sh TSLA
```

### Env

| Var | Purpose |
|-----|---------|
| `XAI_API_KEY` | Optional scripted Grok API (not required for Grok Build UI agents) |
| `XAI_MODEL` | Default `grok-4.5` |
| `XAI_BASE_URL` | Default `https://api.x.ai/v1` |

## Safety

- Hooks must **never** send live broker orders without a separate, explicit execution module.
- Decision artifacts stay under `decisions/` and `journal/` with integrity rules intact.
