---
name: stock-decision
description: >
  Orchestrate a Grok Build multi-agent stock decision: pipeline facts first,
  then multi-turn Bull/Bear debate, Research Manager, and Trader. Use for
  /decide-stock or when the user wants a Grok-authored trade decision grounded
  in local scores/signals. Uses the Grok Build subscription (this session) —
  no XAI_API_KEY required.
---

# Stock Decision (Grok Build subscription)

**Measurement backend:** local Python `scripts/` (never invent numbers).  
**Decision backend:** **this Grok Build session** and project agents (`grok-4.5` / session model).  
**No API key:** do not ask the user for `XAI_API_KEY`. Do not call external xAI HTTP APIs for the normal path.

## Workflow (you are the orchestrator in Grok Build)

1. **Parse** ticker (required), optional profile (`Balanced` default), optional **debate rounds** (default **2**).
   - User may say `AAPL --rounds 3` or `2-round debate`.
2. **Prepare handoff** with local Python only:

```bash
python scripts/prepare_decision_handoff.py TICKER --profile Balanced --fast
# forecasts are OFF by default (research-only). Opt-in: add --forecasts (and not --fast)
# Path C multi-horizon entry is OFF by default. Opt-in: --multi-horizon-entry
```

3. **Read** `decisions/handoff_TICKER.json` (and any `signals_TICKER.json` path inside it).
4. **Summarize** for the user: overall score, **`dual_recommendation`** (Research vs Execute), `policy_hint`, key risks from quant.
   - Never treat Research BUY as a long if Execute is FLAT / `policy_conflict` is true.
5. **Init multi-turn debate transcript:**

```bash
python scripts/debate_session.py init TICKER --rounds 2 --handoff decisions/handoff_TICKER.json
# note the printed path → decisions/debate_TICKER_<ts>.json
```

6. **Multi-turn debate** (default `max_rounds=2` → 4 speaker turns: B1, S1, B2, S2):

   For each round `r = 1 .. max_rounds`:
   - Ask **stock-bull** with:
     - full handoff facts
     - `python scripts/debate_session.py history <path>` (or `bundle`)
     - Bear’s last argument (empty on round 1)
     - Instruction: this is **round r of max_rounds**; rebut prior Bear; cite only handoff numbers
   - Append:  
     `python scripts/debate_session.py append <path> --role bull --round r --text "..."`  
     (or write to a temp file and `--file`)
   - Ask **stock-bear** with handoff + history + Bull’s last argument; round r of max_rounds
   - Append bear turn similarly

   After `debate_session.py next` returns `manager` (or `status` shows `debate_complete`):
   - **stock-research-manager** with full history + handoff
   - Append `--role manager`
   - **stock-trader** with manager plan + handoff + `policy_hint`
   - Append `--role trader`

   Prefer spawning project agents (`.grok/agents/stock-*.md`) or playing roles in-order — all under the **Grok Build subscription**.

7. **Validate** decision JSON (`action`, `conviction`, `rationale`). Reject invented metrics not in the handoff.
8. **Policy cross-check:** if `policy_hint.action` is `flat` and Trader says long/BUY, set `policy_conflict: true` and warn (do not silently override risk filters).
9. **Persist** final package:

```bash
# save decisions/live_TICKER_<timestamp>.json including debate path + final JSON
```

Include in the live decision file: `debate_path`, `debate_rounds`, and ideally embed `turns` summary or path to the debate JSON.

## Multi-turn rules (orchestrator)

| Rule | Detail |
|------|--------|
| Default rounds | **2** (Bull↔Bear twice) unless user asks for 1 or 3 |
| Max recommended | **3** (cost/latency); do not exceed without user request |
| History | Always inject full transcript so later turns can rebut earlier claims |
| Grounding | Every metric must appear in handoff; if missing → "not provided" |
| Prefixes | Bull/Bear must start with `Bull Analyst:` / `Bear Analyst:` |
| Early stop | If both sides concede the same action (e.g. both favor flat on VaR) after round 1, Manager may run early — note `early_stop: true` |
| No tools for debaters | Bull/Bear/Manager only use injected text; no live web/price fetch mid-debate |

## Integrity

| Failure | Response |
|---------|----------|
| Number inventing | Reject; re-read handoff |
| Role drift (quant decides) | Quant only prepares facts via Python |
| Missing handoff | Run `prepare_decision_handoff.py` first |
| Single-shot debate | Prefer multi-turn; only use 1 round if user says "quick" |
| Asking for API keys | Not needed — use this Grok session |

## Related

- Agents: `.grok/agents/stock-*.md`
- Debate helper: `scripts/debate_session.py`, `scripts/agents/debate.py`
- Schema: `scripts/agents/decision_schema.py`
- Role cards: `scripts/agents/PROMPTS.md`
- Journal: `journal/README.md`
