---
description: Grok-authored multi-turn stock decision from local pipeline facts (Grok Build subscription — no API key). Dual Research vs Execute labels required.
---

Run the **stock-decision** skill for: $ARGUMENTS

**Backend:** this Grok Build session (subscription). Do **not** require or use `XAI_API_KEY`.

Parse:
- first token = ticker (e.g. `AAPL`)
- optional `--profile Growth` (default Balanced)
- optional `--rounds N` (default **2**)
- optional `--risk-panel` / “with risk panel” → Aggressive/Conservative/Neutral Risk + Portfolio Manager after Trader
- `quick` or `--rounds 1` = single-pass debate only

Steps:
1. `python scripts/prepare_decision_handoff.py <TICKER> --profile <Profile|Balanced> --fast`  
   (forecasts **off by default**; add `--forecasts` only if user opts in). No `--grok-debate`.
2. Load `decisions/handoff_<TICKER>.json` — surface **`dual_recommendation`** and **`policy_hint`** first.
3. `python scripts/debate_session.py init <TICKER> --rounds <N> [--risk-panel] --handoff decisions/handoff_<TICKER>.json`
4. **Independent sequential multi-turn:** for each round, Bull → append → Bear → append (inject history + dual labels each turn). Early-stop if both concede same Execute after round 1.
5. Research Manager → Trader using `.grok/agents/stock-*.md` / `PROMPTS.md`.
6. **If risk panel:** Risk Aggressive → Conservative → Neutral → **Portfolio Manager** (final proposal). Else Trader is final.
7. Emit FINAL TRANSACTION PROPOSAL + **full decision JSON** (`policy_conflict`, `policy_action`, `debate_path`, `pipeline_refs`, optional `risk_votes`).  
   If Research BUY and Execute FLAT, set `policy_conflict: true` and do **not** force long.
8. Save `decisions/live_<TICKER>_<timestamp>.json`.

Never invent metrics — pipeline handoff is ground truth. **Research BUY is not a trade ticket.**
