---
status: pending
type: policy-rule-proposal
authority: ingestion
created: YYYY-MM-DD
tags: [journal, policy]
---

# Policy rule proposal: <short title>

## Scope

- Code: `scripts/backtest/memory.py` MemoryConfig and/or `policy.py`
- Docs: `journal/rules/current/`

## Intent

What should change and why (risk reduction, less churn, etc.).

## Evidence

Durable sources only:

- `journal/runs/<file>.json` or `backtest_decisions_<TICKER>.json`
- Metrics: total_return, max_drawdown, vs_bh, num_trades (before/after)
- Commit SHA if comparing versions

Weak evidence (chat memory, single lucky day) usually fails the Source gate.

## Authorship

- Agent / human:
- Session / date:

## Proposed rule

Exact change, e.g.:

```
stop_cooldown_days: 5 → 7
post_stop_risk_mult: 0.5 → 0.4
```

Or prose that can be translated 1:1 into `MemoryConfig` fields.

## Gates checklist (for acceptor)

- [ ] Look-ahead safe (no future labels in training window)
- [ ] Walk-forward or held-out tickers/dates
- [ ] Does not hardcode one ticker's scar into global policy without multi-sample check
- [ ] Accepted → update code + `rules/current/` + move this file to `accepted/`
