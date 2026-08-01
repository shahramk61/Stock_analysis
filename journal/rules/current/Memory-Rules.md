---
type: procedure
authority: current
tags: [journal, policy, memory]
last_verified: 2026-07-31
---

# Decision memory — current procedural rules

> [!info] Queries this page answers
> - What does the agent remember between days?
> - What happens after a stop-out?
> - How is loss-streak sizing applied?

## Implementation

Source of truth in code: `scripts/backtest/memory.py` → `MemoryConfig`.

## Current rules

| Rule | Value | Effect |
|------|-------|--------|
| Stop cooldown | 5 calendar days | Block new longs; risk ×0.5 while active |
| Post-stop risk mult | 0.5 | Applied during cooldown |
| Loss streak cut | 2 consecutive losses | risk ×0.5 until a win breaks streak |
| Decision lookback | 10 | Shown in memory summary |
| Trade lookback | 5 closed trades | Shown in memory summary |

## Non-rules (explicit)

- Memory does **not** invent scores, VaR, or conviction.
- Debate prose cannot override cooldown (policy code enforces blocks).
- Pending proposals under `journal/rules/pending/` are not live.

## Change control

Use `journal/rules/TEMPLATE.md` → pending → evidence → accepted + code change.
