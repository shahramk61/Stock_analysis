# Decision Journal (Abzu-inspired)

Episodic memory of agent decisions and trade outcomes for Stock Analysis.
**Not** a free-form LLM diary — only pipeline-recorded facts.

## Authority (like Abzu Vault)

| Path | Authority | Who writes |
|------|-----------|------------|
| `runs/*.json` | **episodic** (one backtest/live run) | Backtester / CLI |
| `rules/current/` | **current** procedural policy | Human after gates |
| `rules/pending/` | **ingestion** (not truth) | Any agent proposing rule changes |
| `rules/accepted/` | archive of promoted proposals | Human / process |
| `rules/rejected/` | failed proposals + reasons | Human / process |

**Ingestion is not knowledge.** Files under `rules/pending/` must not be cited as live policy until promoted to `rules/current/`.

## Hard look-ahead rule

When injecting memory into a decision at date `D`:

- Decisions with `date <= D` only
- Closed trades with `exit_date <= D` only
- Open position state is allowed (known at `D`)
- **Never** use future PnL or future exits

## What gets stored (runs)

From the engine:

- Decisions: date, action, score, conviction, rationale, stop
- Trades: entry/exit, costs, exit_reason, pnl, decision_date
- Snapshots: asof memory view used at each decision (flags, risk_multiplier)

## Default procedural rules (`MemoryConfig`)

These are **current** code defaults (also documented here):

1. **Stop cooldown** — after a stop-out, no new long for **5 calendar days**; size ×0.5 while cooling.
2. **Loss streak** — after **2** consecutive realized losses, size ×0.5 until a win.

Changing these requires a pending proposal + evidence (backtest export paths), not a chat vibe.

## How to propose a rule change

1. Copy `rules/TEMPLATE.md` → `rules/pending/YYYY-MM-DD-<slug>.md`
2. Fill Scope, Intent, Evidence, Authorship, Proposed rule
3. Stop — do not edit `MemoryConfig` until accepted
4. After walk-forward evidence looks good: move to `accepted/` and update code + `rules/current/`

## Agent usage

- Backtest: `--memory` (default on) injects snapshot into policy + quant state
- Quant debate may include a **facts-only** `[Decision Memory asof …]` block
- Policy applies cooldown / size cuts via `memory` dict — code, not prose

## Evaluation

```bash
python tests/test_decision_memory.py
python scripts/backtest.py AAPL --start 2026-06-30 --end 2026-07-31 --fast --memory --export
```
