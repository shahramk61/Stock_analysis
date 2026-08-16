# Risk Toolkit

Risk-owned trade vetting: **ALLOW / CUT / VETO**.

## Authority

Risk owns **size** and the **veto**. Research BUY labels do not override a VETO.

## Mandate: Fail Closed

Missing, non-point-in-time, or live-leaking data → **VETO**.

## Machine-Readable Veto Object

Both the Risk gate (`vet_trade`) and the inherited policy path (`default_policy`) expose a **`risk_veto`** object with stable keys for Trader consumption. Trader branches on `decision` only: `ALLOW` = size as given, `CUT` = use `risk_pct` (already reduced), `VETO` = do not enter / flatten (`risk_pct=0`). Schema: `{"decision": "ALLOW"|"CUT"|"VETO", "reason": "<one-line>", "reasons": [...], "missing": ["var_95",...], "risk_pct": <float>, "action": "long"|"flat", "ticker": "...", "asof": "YYYY-MM-DD"}`. Access via `RiskDecision.to_veto_object()` or `TradeSignal.risk_veto`.

## Usage

```python
from risk import vet_trade, size_position

# Vet a proposed long
decision = vet_trade(
    action="long",
    ticker="AAPL",
    asof="2026-08-15",
    proposed_risk_pct=0.01,
    var_95=22.5,              # from pipeline mc_risk (required)
    regime="Neutral",         # from signals.regime.regime (required)
    structural_breakdown=False,
    clear_uptrend=True,
    memory_snapshot=memory_dict,  # from DecisionMemory.apply_to_policy_inputs()
)

if decision.vetoed():
    print(f"VETO: {[r.detail for r in decision.reasons]}")
elif decision.cut():
    print(f"CUT: risk {decision.risk_pct} (from {0.01})")
else:
    print(f"ALLOW: risk {decision.risk_pct}")

# Size the position (returns 0 if vetoed)
shares = size_position(
    decision,
    equity=100_000,
    price=150.0,
    stop_price=142.0,
)
```

## Required Fields for New Longs

| Field | Source | Missing → |
|-------|--------|-----------|
| `asof` | Decision date (YYYY-MM-DD) | VETO |
| `var_95` | `mc_risk.var_95` from pipeline | VETO |
| `regime` | `signals.regime.regime` | VETO |

## Veto Conditions

| Condition | Action |
|-----------|--------|
| Missing required field | **VETO** |
| `live_leak=True` | **VETO** (lookahead contamination) |
| `fundamentals_pit=False` | **VETO** (lookahead contamination) |
| Bear regime | **VETO** (capital protection) |
| VaR > 45% | **VETO** (extreme risk) |
| VaR > 30% + structural breakdown | **VETO** |
| VaR > 30% without clear uptrend | **VETO** |
| Stop cooldown active | **VETO** (memory) |
| Missing CVaR | **VETO** (always checked) |
| Proposed notional > 0 and book is None | **VETO** (concentration) |
| Single-name weight > 25% | **VETO** (concentration) |
| Correlated cluster > 40% | **VETO** (concentration) |

## Size Cuts (CUT = allowed but reduced)

| Condition | Multiplier |
|-----------|------------|
| VaR > 30% with clear uptrend | ×0.30 |
| VaR > 20% (elevated) | ×0.50 |
| Loss streak ≥ 2 | ×0.50 (from memory) |

Cuts multiply: VaR cut (×0.5) + memory cut (×0.5) → ×0.25 total.

## VaR Ladder

Sourced from `backtest.policy`:

- **Elevated** (>20%): size cut
- **High** (>30%): deep cut unless constructive structure → flat without clear uptrend
- **Extreme** (>45%): hard flat regardless of trend/regime

## Memory Integration

Pass `memory_snapshot` from `DecisionMemory.apply_to_policy_inputs()`:

```python
mem = DecisionMemory(ticker="AAPL", config=MemoryConfig(stop_cooldown_days=5))
# ... record trades ...
snap = mem.snapshot_asof("2026-08-15", position=100, entry_price=150.0)
memory_dict = mem.apply_to_policy_inputs(snap)

decision = vet_trade(..., memory_snapshot=memory_dict)
```

Memory rules:
- **Stop cooldown** (5 days after stop-out): VETO new longs
- **Loss streak** ≥2: CUT (×0.5 risk)

## Concentration Limits (Risk-Ratified)

**Authority**: Risk CoS. Do not invent other limits.

Ratified limits (enforced fail-closed):
- **Single name** ≤ 10% of book
- **Sector** ≤ 25%
- **Factor cluster** ≤ 35% (corr > 0.60; pending Quant PIT return matrix)
- **Cash** ≥ 10% (not yet enforced)
- **Max names** ≤ 20

PM state requirements:
- `book_ready=false` → VETO new adds (paper book must be ready)
- Empty book → VETO new adds (cannot verify limits)

### Enforcement

```python
book = {
    "AAPL": {"notional": 50_000, "sector": "Technology"},
    "MSFT": {"notional": 30_000, "sector": "Technology"},
}
sector_tags = {"GOOGL": "Technology"}  # required for sector check
correlations = {("AAPL", "GOOGL"): 0.65, ...}  # required for factor cluster

decision = vet_trade(
    ...,
    book=book,
    book_ready=True,  # PM state flag
    sector_tags=sector_tags,  # required
    correlations=correlations,  # required (Quant PIT return matrix)
    proposed_notional=20_000,
)
```

**Missing data → VETO (fail closed)**:
- `book_ready=false` → VETO
- Missing sector tag on add → VETO (cannot prove sector cap)
- Missing correlation on **multi-name add** (post-add ≥2 names) → VETO

**CoS exception (prevent deadlock on empty funded book)**:
- **First add** to empty/cash-only book: skip concentration checks (concentration undefined on single-name book)
- Factor cluster check requires post-add ≥2 names (correlation undefined on 1-name book)
- First add + missing correlation → ALLOW (cannot deadlock)
- Second add + missing correlation → VETO (fail closed on multi-name book)

**Never invented**:
- Do NOT treat missing correlation as 0
- Do NOT invent sector tags
- Limits are in `scripts/risk/limits.py` (CONCENTRATION_LIMITS constant)

## CVaR (Conditional Value at Risk)

**Desk Policy (Risk-Ratified): CVaR is ALWAYS checked.** Missing CVaR → VETO.

```python
decision = vet_trade(
    ...,
    cvar_95=22.5,         # from MC sim (REQUIRED, must be real, not fallback)
    mc_metadata={"paths": 10000, "simulations": 252},  # MC evidence
)
```

**Hard rule from CoS/Quant**: CVaR must be from actual Monte Carlo sim, not fallback.

- CVaR check is enforced on every trade (not opt-in)
- Quant pipeline must emit `cvar_95` from MC sim; missing → VETO

**Fallback detection**:
- CVaR in {20.0, 28.0} (old helper fallbacks) without MC evidence → **treat as missing → VETO**
- MC evidence: `mc_metadata` with `paths > 0` or `simulations > 0` and no `is_fallback` flag
- CVaR not in {20.0, 28.0} → no fallback check needed
- Never invent CVaR. Never fill from fallbacks.

## Integration with Existing Policy

The Risk toolkit does **not** replace `backtest.policy.default_policy`. It adds a fail-closed veto layer.

Recommended flow:

1. Run existing pipeline (score, signals, mc_risk, regime, etc.)
2. Call `default_policy` to get proposed action + risk_pct + rationale
3. Call `vet_trade` with policy output + point-in-time bundle
4. If vetoed: log veto reasons, stay flat
5. If cut/allowed: use vetted `risk_pct` for position sizing

## What Risk Does NOT Do

- Does **not** invent VaR, CVaR, regime, prices, scores, or stops
- Does **not** run forecasts / multi-horizon Path C by default
- Does **not** change Research BUY labels (dual labels remain)
- Does **not** add a live broker

## Tests

```bash
python3 tests/test_risk_gate.py
```

Covers:
- Missing VaR/regime/asof → VETO
- Lookahead flags → VETO
- Bear regime → VETO
- VaR ladder (extreme/high/elevated) → VETO or CUT
- Memory (cooldown → VETO, loss streak → CUT)
- Concentration (missing book, single-name cap, cluster cap) → VETO
- Research BUY + Execute VETO → stays FLAT
- Position sizing returns 0 on VETO

## Design

- **gate.py**: Core veto logic (`vet_trade`, `RiskDecision`, `VetoReason`)
- **sizing.py**: Position sizing wrapper (`size_position`)
- **__init__.py**: Public API exports

## Notes

- VaR/CVaR thresholds and concentration caps are policy constants (Risk authority).
- If no in-repo concentration limits exist, we use documented defaults (25% single-name, 40% cluster).
- Structural breakdown: death cross / Bearish stack (from policy leverage flags).
- Clear uptrend: Bullish stack / golden cross (from policy leverage flags).

## Future

- CVaR threshold once Quant pipeline emits it consistently
- Dynamic concentration caps per regime / volatility regime
- Cross-asset correlation (if desk expands beyond equities)
