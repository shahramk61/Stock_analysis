---
name: stock-decision
description: >
  Orchestrate a Grok Build multi-agent stock decision: pipeline facts first,
  then Bull/Bear/Manager/Trader roles. Use for /decide-stock or when the user
  wants a Grok-authored trade decision grounded in local scores/signals.
  Uses the Grok Build subscription (this session) — no XAI_API_KEY required.
---

# Stock Decision (Grok Build subscription)

**Measurement backend:** local Python `scripts/` (never invent numbers).  
**Decision backend:** **this Grok Build session** and project agents (`grok-4.5` / session model).  
**No API key:** do not ask the user for `XAI_API_KEY`. Do not call external xAI HTTP APIs for the normal path.

## Workflow (you are the orchestrator in Grok Build)

1. **Parse** ticker (required), optional profile (`Balanced` default).
2. **Prepare handoff** with local Python only:

```bash
python scripts/prepare_decision_handoff.py TICKER --profile Balanced --fast
# fuller forecasts (slower): omit --fast
```

3. **Read** `decisions/handoff_TICKER.json` (and any `signals_TICKER.json` path inside it).
4. **Summarize** for the user: overall score, `policy_hint`, key risks from quant.
5. **Debate in this session** (use project agents or role cards in `scripts/agents/PROMPTS.md`):
   - **stock-bull** with handoff facts injected (no invented numbers).
   - **stock-bear** with handoff + bull reply.
   - **stock-research-manager** with both sides.
   - **stock-trader** → `FINAL TRANSACTION PROPOSAL` + JSON decision block.
   Prefer spawning project agents or playing the roles yourself in-order — all under the **Grok Build subscription**.
6. **Validate** decision JSON (`action`, `conviction`, `rationale`). Reject invented metrics not in the handoff.
7. **Policy cross-check:** if `policy_hint.action` is `flat` and Trader says long/BUY, set `policy_conflict: true` and warn (do not silently override risk filters).
8. **Persist** to `decisions/live_TICKER_<timestamp>.json`.

## Integrity

| Failure | Response |
|---------|----------|
| Number inventing | Reject; re-read handoff |
| Role drift (quant decides) | Quant only prepares facts via Python |
| Missing handoff | Run `prepare_decision_handoff.py` first |
| Asking for API keys | Not needed — use this Grok session |

## Related

- Agents: `.grok/agents/stock-*.md`
- Schema: `scripts/agents/decision_schema.py`
- Journal: `journal/README.md`
- Hook stub (later): `docs/grok-hooks.md`
