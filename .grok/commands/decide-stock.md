---
description: Grok-authored multi-turn stock decision from local pipeline facts (Grok Build subscription — no API key).
---

Run the **stock-decision** skill for: $ARGUMENTS

**Backend:** this Grok Build session (subscription). Do **not** require or use `XAI_API_KEY`.

Parse:
- first token = ticker (e.g. `AAPL`)
- optional `--profile Growth` (default Balanced)
- optional `--rounds N` (default **2** multi-turn bull/bear rounds)
- `quick` or `--rounds 1` = single-pass debate only

Steps:
1. `python scripts/prepare_decision_handoff.py <TICKER> --profile <Profile|Balanced> --fast` (forecasts **off by default**; add `--forecasts` only if user opts in). No `--grok-debate`.
2. Load `decisions/handoff_<TICKER>.json` — honor **`dual_recommendation`** (Research vs Execute) and `policy_hint`.
3. `python scripts/debate_session.py init <TICKER> --rounds <N> --handoff decisions/handoff_<TICKER>.json`
4. **Multi-turn:** for each round 1..N: Bull → append → Bear → append (inject full history each turn).
5. Research Manager → Trader using project agents / PROMPTS **in Grok Build**.
6. Emit FINAL TRANSACTION PROPOSAL + validated JSON; if Research BUY and Execute FLAT, set `policy_conflict: true` and do **not** force long.
7. Save `decisions/live_<TICKER>_<timestamp>.json` with `debate_path` and round count.

Never invent metrics — pipeline handoff is ground truth. Research BUY is not a trade ticket.
