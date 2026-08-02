# Grok Build automation (subscription path)

**Decision backend = Grok Build (your subscription).**  
No `XAI_API_KEY` is required for normal use.

## Today

| Trigger | How |
|---------|-----|
| Manual decision | `/decide-stock TICKER` in this Grok Build chat |
| Facts only (no LLM) | `python scripts/prepare_decision_handoff.py TICKER --fast` (forecasts off by default) |
| Agents | `.grok/agents/stock-*.md` (run as Grok Build agents/subagents) |
| Research vs Execute | Always read `dual_recommendation` + `policy_hint` in handoff — Research BUY ≠ order |

## Do not use for the primary path

| Avoid | Why |
|-------|-----|
| `XAI_API_KEY` / `scripts/agents/llm/grok_client.py` | Separate HTTP API billing; not your Grok Build subscription |
| `--grok-debate` on handoff | Optional API rephrase only; skip it |

The `grok_client.py` module remains only for rare offline/script experiments. Prefer in-session Grok for all debate and decisions.

## Later (opt-in automation)

Still **inside Grok Build**, not the public API:

1. **Scheduled task / workflow** in Grok that runs prepare + decide for a watchlist  
2. **Project-local hook** only if the user creates an opt-in flag (never default-on)  
3. **Post-backtest** prompt: offer `/decide-stock` using journal memory  

### Stub (facts only)

```bash
./scripts/hooks/run_decide_stock.sh TSLA
# → prepares handoff, then tells you to run /decide-stock in Grok Build
```

## Safety

- No live broker orders without a separate execution module.  
- Artifacts under `decisions/` and `journal/` only.  
