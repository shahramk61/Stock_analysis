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
| Missing CVaR when `require_cvar=True` | **VETO** (opt-in) |
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

## Concentration / Correlation

Optional checks when `book` (current positions) and/or `correlations` are provided:

```python
book = {"AAPL": 50_000, "MSFT": 30_000}  # {ticker: notional}
correlations = {("AAPL", "GOOGL"): 0.85, ...}  # {(t1, t2): corr}

decision = vet_trade(
    ...,
    book=book,
    correlations=correlations,
    proposed_notional=20_000,
)
```

- If `proposed_notional > 0` and `book is None` → VETO (can't verify concentration)
- If ticker already in book → skip concentration check (existing position)
- Single-name cap: 25% of total book
- Cluster cap: 40% for names with pairwise correlation > 0.70

## CVaR (Conditional Value at Risk)

Opt-in fail-closed check:

```python
decision = vet_trade(
    ...,
    cvar_95=28.0,         # from pipeline (if available)
    require_cvar=True,    # opt-in: missing CVaR → VETO
)
```

If `require_cvar=False` (default): missing CVaR is OK (check not enforced).
If `require_cvar=True`: Quant pipeline must emit `cvar_95`; missing → VETO.

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
