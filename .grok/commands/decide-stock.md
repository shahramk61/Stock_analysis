---
description: Grok-authored stock decision from local pipeline facts (uses Grok Build subscription — no API key).
---

Run the **stock-decision** skill for: $ARGUMENTS

**Backend:** this Grok Build session (subscription). Do **not** require or use `XAI_API_KEY`.

Parse the first token as ticker (e.g. `AAPL` or `TSLA --profile Growth`).

Steps:
1. `python scripts/prepare_decision_handoff.py <TICKER> --profile <Profile|Balanced> --fast` (drop `--fast` if user wants full forecasts). No `--grok-debate`.
2. Load `decisions/handoff_<TICKER>.json`.
3. Bull → Bear → Research Manager → Trader using project agents / PROMPTS **in Grok Build**.
4. Emit FINAL TRANSACTION PROPOSAL + validated JSON; note any policy_hint conflict.
5. Save `decisions/live_<TICKER>_<timestamp>.json`.

Never invent metrics — pipeline handoff is ground truth.
