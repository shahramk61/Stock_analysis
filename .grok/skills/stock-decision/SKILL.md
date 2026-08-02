---
name: stock-decision
description: >
  Orchestrate a Grok Build multi-agent stock decision: pipeline facts first,
  then independent sequential multi-turn Bull/Bear debate, Research Manager,
  and Trader. Dual Research vs Execute labels are mandatory. Uses Grok Build
  subscription — no XAI_API_KEY required.
---

# Stock Decision (Grok Build subscription)

**Measurement backend:** local Python `scripts/` (never invent numbers).  
**Decision backend:** **this Grok Build session** and project agents.  
**No API key:** do not ask for `XAI_API_KEY` or call external xAI HTTP APIs for the normal path.

## Workflow (you are the orchestrator)

1. **Parse** ticker (required), optional profile (`Balanced` default), optional **debate rounds** (default **2**).
2. **Prepare handoff** (local Python only):

```bash
python scripts/prepare_decision_handoff.py TICKER --profile Balanced --fast
# forecasts OFF by default; opt-in: --forecasts
# Path C multi-horizon entry OFF by default; opt-in: --multi-horizon-entry
```

3. **Read** `decisions/handoff_TICKER.json`.
4. **Summarize for the user first:**
   - overall score  
   - **`dual_recommendation`** (`Research X | Execute Y`, `policy_conflict`)  
   - `policy_hint` (action, conviction, risk, stop)  
   - key quant risks (VaR, regime, death cross)  
   - **Never treat Research BUY as a long if Execute is FLAT.**

5. **Init debate transcript:**

```bash
python scripts/debate_session.py init TICKER --rounds 2 --handoff decisions/handoff_TICKER.json
# → decisions/debate_TICKER_<ts>.json
```

6. **Multi-turn debate — independent sequential turns (required)**

   Do **not** author all six roles in one batch with identical timestamps.  
   For each speaker: inject fresh context → generate **that role only** → append → then next.

   **Injection every turn** (named placeholders from `scripts/agents/PROMPTS.md`):
   - `{dual_recommendation}`, `{policy_hint}`, `{overall_score}`
   - `{quantitative_report}` / key quant fields from handoff
   - `{debate_history}` via `python scripts/debate_session.py history <path>`
   - `{bear_last_argument}` / `{bull_last_argument}` from bundle
   - `{round}`, `{max_rounds}`, `{debate_path}`

   For each round `r = 1 .. max_rounds`:
   1. **stock-bull** (or role card) with placeholders above  
   2. `debate_session.py append <path> --role bull --round r --file …`  
   3. **stock-bear** with updated history  
   4. `append --role bear --round r …`

   **Early stop:** If after round 1 both Standing views imply the same Execute outcome  
   (e.g. both stand-down / both defensive flat on VaR+Bear), skip further Bull/Bear rounds.  
   Set `early_stop: true` on the live decision. Proceed to Manager.

   When `debate_session.py next` → `manager` (or early stop):
   1. **stock-research-manager** with full history + dual labels  
   2. `append --role manager`  
   3. **stock-trader** with manager plan + dual + policy_hint  
   4. `append --role trader`

   Prefer **spawning** `.grok/agents/stock-*.md` as separate role invocations when the harness supports it.

7. **Validate** decision JSON against required fields (`ticker`, `action`, `conviction`, `rationale`).  
   Prefer full schema: `policy_action`, `policy_conflict`, `debate_path`, `debate_rounds`, `early_stop`, `pipeline_refs`, `schema_version`, `overall_score`, `stop_price`, `suggested_risk_pct`.
8. **Policy cross-check:** if `policy_hint.action` is `flat` and Trader says long/BUY → force `policy_conflict: true`, warn user, prefer flat unless user overrides.
9. **Persist** `decisions/live_TICKER_<timestamp>.json` with debate path + dual snapshot.

## Multi-turn rules (orchestrator)

| Rule | Detail |
|------|--------|
| Default rounds | **2** unless user asks 1 or 3 |
| Max recommended | **3** |
| Independent turns | One role per generation; append before next |
| History | Full transcript every turn |
| Grounding | Metrics only from handoff; missing → "not provided" |
| Dual labels | Research ≠ Execute; conflict → do not force long |
| Cross-ticker | Banned unless in handoff |
| Prefixes | `Bull Analyst:` / `Bear Analyst:` |
| Early stop | Mutual Execute concession after round 1 → Manager |
| No tools mid-debate | Bull/Bear/Manager: injected text only |

## Integrity failures

| Failure | Response |
|---------|----------|
| Number inventing | Reject; re-read handoff |
| Research BUY as order | Follow Execute / policy_hint |
| Role drift (quant decides) | Quant = facts via Python only |
| Missing handoff | Run `prepare_decision_handoff.py` first |
| Batch fake multi-agent | Re-run with sequential appends |
| Asking for API keys | Not needed — this Grok session |

## Related

- Agents: `.grok/agents/stock-*.md`
- Static cards: `scripts/agents/PROMPTS.md`
- Debate CLI: `scripts/debate_session.py`, `scripts/agents/debate.py`
- Schema: `scripts/agents/decision_schema.py`
- Dual labels: `scripts/recommendation.py`
- Journal: `journal/README.md`
