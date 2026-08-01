---
description: Grok-authored stock decision from local pipeline facts (Bull/Bear/Manager/Trader).
---

Run the **stock-decision** skill for: $ARGUMENTS

Parse the first token as ticker (e.g. `AAPL` or `TSLA --profile Growth`).

Steps:
1. `python scripts/prepare_decision_handoff.py <TICKER> --profile <Profile|Balanced> --fast` (drop `--fast` if user wants full forecasts).
2. Load `decisions/handoff_<TICKER>.json`.
3. Run Bull → Bear → Research Manager → Trader using project agents / PROMPTS (Grok Build backend, model grok-4.5).
4. Emit FINAL TRANSACTION PROPOSAL + validated JSON; note any policy_hint conflict.
5. Save `decisions/live_<TICKER>_<timestamp>.json`.

Never invent metrics — pipeline handoff is ground truth.
