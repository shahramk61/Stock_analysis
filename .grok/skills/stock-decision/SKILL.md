---
name: stock-decision
description: >
  Orchestrate a Grok Build multi-agent stock decision: pipeline facts first,
  then Bull/Bear/Manager/Trader roles. Use for /decide-stock or when the user
  wants a Grok-authored trade decision grounded in local scores/signals.
---

# Stock Decision (Grok Build backend)

**Measurement backend:** local Python `scripts/` (never invent numbers).  
**Decision backend:** **Grok Build** agents (`grok-4.5`).  
**Optional API path:** `XAI_API_KEY` + `scripts/agents/llm/grok_client.py` for quant rephrase only.

## Workflow (orchestrator — you are main Grok session)

1. **Parse** ticker (required), optional profile (`Balanced` default).
2. **Prepare handoff** (facts only):

```bash
python scripts/prepare_decision_handoff.py TICKER --profile Balanced --fast
# fuller forecasts (slower):
# python scripts/prepare_decision_handoff.py TICKER --profile Balanced
```

3. **Read** `decisions/handoff_TICKER.json` (and `signals_TICKER.json` if referenced).
4. **Summarize** for the user: overall score, policy_hint, key risks from quant.
5. **Debate** (use project agents or role cards in `scripts/agents/PROMPTS.md`):
   - Spawn / role-play **stock-bull** with handoff injected.
   - Spawn / role-play **stock-bear** with handoff + bull reply.
   - **stock-research-manager** with both sides.
   - **stock-trader** → `FINAL TRANSACTION PROPOSAL` + JSON.
6. **Validate** decision JSON (action, conviction, rationale). Flag if numbers appear that are not in the handoff.
7. **Policy cross-check:** if `policy_hint.action` is `flat` and Trader says long/BUY, mark `policy_conflict: true` and warn the user (do not silently override risk filters).
8. **Persist** to `decisions/live_TICKER_<timestamp>.json`.

## Integrity

| Failure | Response |
|---------|----------|
| Number inventing | Reject; re-read handoff |
| Role drift (quant decides) | Quant only prepares facts |
| Missing handoff | Run prepare_decision_handoff first |
| No API key | Fine for Grok Build path; API only for --grok-debate |

## Related

- Agents: `.grok/agents/stock-*.md`
- Schema: `scripts/agents/decision_schema.py`
- Journal memory: `journal/README.md`
- Future automation: `docs/grok-hooks.md`
