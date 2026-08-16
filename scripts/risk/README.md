# Risk Management - Book Constraint Model

**Updated: August 2026**

## Executive Summary

Risk management for Shahram's thematic paper fund is built around **fund-level book constraints**:
- **Liquidity**: Position size vs. average daily volume
- **Concentration**: Single name, sector/theme, factor cluster limits
- **Cash**: Minimum cash buffer (10% floor)
- **Name/theme purity**: Maximum 20 names, theme tags required
- **Stranded book checks**: FLAG exits that would orphan themes or create liquidity holes

### What Changed

**RETIRED**: Daily stock-level VaR/CVaR/regime flatten walk (July 2026 model in PR #4).

**NEW**: Fund-level book constraint gate that validates tickets against concentration, liquidity, and purity rules. Does **not** veto CIO-approved HOLDs based on VaR, death cross, or Bear regime—those are research signals, not fund-level risk.

---

## Design Philosophy

1. **Fail closed**: Missing NAV, missing asof marks, or missing liquidity data → BLOCK (do not invent numbers)
2. **HOLD passes through**: Do NOT veto HOLDs (especially CIO-approved) for VaR, CVaR, Bear regime, or death cross. Thesis risk belongs to Theme Research and the CIO.
3. **BUY/ADD constraints**: Block if violates cash, name, sector/theme, liquidity, or theme purity
4. **TRIM/SELL flags**: Allow by default but FLAG if exit would strand the book (cash floor, name count, orphan theme, liquidity hole)
5. **Research vs. Risk**: Research BUY signals, overnight VaR, death cross do **not** authorize or block a hold by themselves

---

## Constraint Limits

Defined in `scripts/risk/limits.py`:

| Constraint | Limit | Notes |
|------------|-------|-------|
| Min cash | 10% of NAV | Pre-trade check |
| Max single name | 10% of NAV | Post-trade weight (dollar-based, supports fractional shares) |
| Max sector/theme | 25% of NAV | Post-trade exposure |
| Max factor cluster | 35% of NAV | Correlated positions (requires correlation data for multi-name ADD) |
| **Max option sleeve** | **20% of NAV** | **Names marked by Coverage/CIO as missing 15% five-year hurdle** |
| **Sleeve ≤ core balance** | **Sleeve $ ≤ core $** | **Desk-locked 2026-08-16: sleeve dollars may not exceed core dollars** |
| Max names | 20 | Total positions in book |
| Liquidity | Position < ADV / 20 | For liquid exit; fail closed if ADV missing |
| Theme purity | Required | All positions must have theme tag |
| **Book completeness** | **< 5 names AND > 50% cash** | **FLAG (not BLOCK) for under-investment; dies when CIO sized or cash memo** |

### Special Rules

- **Fractional shares**: Check dollar weight vs. 10% name cap, not whole-share count. Don't block a BUY if the ticket notional is ≤10% of NAV, even if 1 share costs more than 10% of NAV.
- **Option sleeve**: Only count positions where Coverage/CIO has marked `option_sleeve=True` OR `hurdle_15pct="miss"`. If the mark is missing, do NOT guess—do not count toward sleeve.
- **Sleeve-core balance** (desk-locked 2026-08-16): Sleeve $ may not exceed core $. BLOCK sleeve ADD that would make sleeve > core. If book already in breach: FLAG (warning), do NOT flatten, do NOT force SELL. BLOCK further sleeve ADD until balanced (CIO trims sleeve or adds core). HOLDs pass through (not flattened).
- **Book completeness FLAG** (desk-locked 2026-08-16, Risk postmortem round 2): FLAG when n_names < 5 AND cash_pct > 50% (under-invested). Never BLOCK on this. The FLAG dies (not emitted) when CIO has sized the book (`cio_sized=True`) or written a cash memo (`cash_memo=True`). Default: FLAG (fail closed).
- **First add exception**: First BUY into a new name does **not** require correlation data
- **Multi-name ADD**: Requires correlation data to validate factor cluster exposure
- **Stranded book**: TRIM/SELL that would drop below 3 names or orphan a theme → FLAG (not BLOCK)

---

## Usage

### Basic Example

```python
from scripts.risk import Book, Position, check_book_constraints

# Define current book state
positions = [
    Position("AAPL", weight_pct=8.0, theme="Tech", liquidity_adv=500_000_000),
    Position("MSFT", weight_pct=7.0, theme="Tech", liquidity_adv=400_000_000),
]

book = Book(
    nav=1_000_000,
    cash=500_000,
    positions=positions,
    asof="2026-08-16",
)

# Validate a BUY ticket
decision = check_book_constraints(
    ticker="GOOGL",
    ticket_type="BUY",
    book=book,
    proposed_weight_pct=8.0,
    theme="Tech",
    liquidity_adv=300_000_000,
    correlation_data={"AAPL": 0.3, "MSFT": 0.4},  # Low correlation
)

print(decision.decision)  # "ALLOW" | "BLOCK" | "FLAG"
print(decision.reason)
print(decision.to_dict())
```

### CIO-Approved HOLD

```python
# CIO-approved hold with death cross / high VaR should ALLOW
decision = check_book_constraints(
    ticker="GME",
    ticket_type="HOLD",
    book=book,
    cio_approved=True,
)

assert decision.decision == "ALLOW"
assert decision.cio_approved == True
# Book constraints do NOT veto holds for VaR/regime
```

### Fractional Shares

```python
# Fractional shares: check dollar weight, not share count
# NAV $3000, TSLA at $342/share, ticket $300 (fractional 0.877 shares)
book = Book(nav=3000, cash=1500, asof="2026-08-16")

decision = check_book_constraints(
    ticker="TSLA",
    ticket_type="BUY",
    book=book,
    proposed_notional=300,  # $300 / $3000 = 10% → ALLOW
    theme="EV",
    liquidity_adv=100_000_000,
)

assert decision.decision == "ALLOW"
# Don't block just because 1 share > 10% NAV if the ticket notional is ≤10%
```

### Option Sleeve Cap

```python
# Option sleeve: max 20% NAV for names marked as missing 15% hurdle
# Only count positions where Coverage/CIO has marked:
#   - option_sleeve=True, OR
#   - hurdle_15pct="miss"
# Do not invent marks; if missing, do not count toward sleeve

positions = [
    Position("SPEC1", weight_pct=8.0, option_sleeve=True),  # Counts
    Position("SPEC2", weight_pct=7.0, hurdle_15pct="miss"),  # Counts
    Position("CORE", weight_pct=10.0),  # Does NOT count (unmarked)
]
book = Book(nav=1_000_000, cash=500_000, positions=positions, asof="2026-08-16")

# Current option sleeve: 8% + 7% = 15%
assert book.option_sleeve_exposure() == 15.0

# Try to add 8% more marked name → would be 23% → BLOCK
decision = check_book_constraints(
    ticker="SPEC3",
    ticket_type="BUY",
    book=book,
    proposed_weight_pct=8.0,
    theme="Speculative",
    liquidity_adv=30_000_000,
    option_sleeve=True,  # Coverage/CIO mark
)

assert decision.decision == "BLOCK"
assert any("option sleeve" in r.lower() for r in decision.reasons)
```

### Book Completeness FLAG

```python
# Book completeness FLAG: warn when under-invested
# FLAG when n_names < 5 AND cash_pct > 50% (idle capital)
# Never BLOCK - this is a warning only
# The FLAG dies when CIO has sized the book or written a cash memo

positions = [
    Position("AAPL", weight_pct=10.0, theme="Tech", liquidity_adv=500000000),
    Position("XOM", weight_pct=10.0, theme="Energy", liquidity_adv=200000000),
]
book = Book(nav=1_000_000, cash=800_000, positions=positions, asof="2026-08-16")

# 2 names < 5, 80% cash > 50% → should FLAG for under-investment
decision = check_book_constraints(
    ticker="GOOGL",
    ticket_type="BUY",
    book=book,
    proposed_weight_pct=8.0,
    theme="Cloud",
    liquidity_adv=300_000_000,
    correlation_data={"AAPL": 0.3, "XOM": 0.1},
    cio_sized=False,  # No CIO sizing yet
)

# Should FLAG (not BLOCK) with completeness warning
assert decision.decision == "FLAG"
assert any("completeness" in r.lower() for r in decision.reasons)
assert any("under-invested" in r.lower() for r in decision.reasons)

# After CIO sizes the book → no completeness FLAG
decision2 = check_book_constraints(
    ticker="GOOGL",
    ticket_type="BUY",
    book=book,
    proposed_weight_pct=8.0,
    theme="Cloud",
    liquidity_adv=300_000_000,
    correlation_data={"AAPL": 0.3, "XOM": 0.1},
    cio_sized=True,  # CIO has sized
)

assert decision2.decision == "ALLOW"  # No flag
```

### Sleeve-Core Balance

```python
# Sleeve-core balance rule (desk-locked 2026-08-16)
# Sleeve dollars may not exceed core dollars

# Live example: NAV $3000, SYM core $298.90, TSLA sleeve $300, WRD sleeve $300
positions = [
    Position("SYM", weight_pct=9.96, notional=298.90, theme="Core", 
            liquidity_adv=100_000_000),  # Core
    Position("TSLA", weight_pct=10.0, notional=300, theme="EV",
            liquidity_adv=150_000_000, option_sleeve=True),  # Sleeve
    Position("WRD", weight_pct=10.0, notional=300, theme="Speculative",
            liquidity_adv=80_000_000, option_sleeve=True),  # Sleeve
]
book = Book(nav=3000, cash=2101.10, positions=positions, asof="2026-08-16")

# Sleeve $600 > core $298.90 → book is in breach
book.sleeve_notional()  # → 600.0
book.core_notional()    # → 298.90

# HOLD on existing position → FLAG (not flatten, not BLOCK)
decision_hold = check_book_constraints(
    ticker="TSLA",
    ticket_type="HOLD",
    book=book,
)
assert decision_hold.decision == "FLAG"
assert any("sleeve" in r.lower() and "core" in r.lower() for r in decision_hold.reasons)
# Do NOT flatten to cure the breach

# Further sleeve ADD → BLOCK (can't add more to sleeve until balanced)
decision_sleeve_add = check_book_constraints(
    ticker="NEWSLV",
    ticket_type="BUY",
    book=book,
    proposed_notional=100,
    option_sleeve=True,
)
assert decision_sleeve_add.decision == "BLOCK"

# Adding core → ALLOW (helps restore balance)
decision_core_add = check_book_constraints(
    ticker="NEWCORE",
    ticket_type="BUY",
    book=book,
    proposed_notional=300,  # 10% NAV
    option_sleeve=False,  # Core position
)
assert decision_core_add.decision in ("ALLOW", "FLAG")  # Not BLOCK
```

### Stranded Book Check (TRIM/SELL)

```python
# Selling the last Energy position orphans the theme
positions = [
    Position("AAPL", weight_pct=30.0, theme="Tech"),
    Position("XOM", weight_pct=20.0, theme="Energy"),  # Only Energy position
    Position("JPM", weight_pct=20.0, theme="Finance"),
]

book = Book(nav=1_000_000, cash=300_000, positions=positions, asof="2026-08-16")

decision = check_book_constraints(
    ticker="XOM",
    ticket_type="SELL",
    book=book,
)

# Should FLAG (not block) because Energy theme would be orphaned
assert decision.decision == "FLAG"
```

### Legacy Veto Object Format

```python
# Convert to Trader/PM veto object format
veto_obj = decision.to_veto_object()
# {
#   "action": "ALLOW" | "BLOCK" | "FLAG",
#   "ticker": "GOOGL",
#   "ticket_type": "BUY",
#   "reason": "...",
#   "details": {
#     "reasons": [...],
#     "missing": [...],
#     "asof": "2026-08-16",
#     "cio_approved": False,
#   }
# }
```

---

## Decision Types

### ALLOW
Ticket passes all book constraints. Trader/PM may proceed.

### BLOCK
Ticket violates hard constraints:
- Missing NAV or asof (fail closed)
- Missing liquidity ADV for BUY/ADD
- Missing theme tag (purity violation)
- Exceeds single name, sector/theme, or factor cluster limits
- Exceeds max names (20)
- Post-trade cash below 10% floor
- Missing correlation data for multi-name ADD

### FLAG
Ticket (usually TRIM/SELL) would strand the book:
- Post-trade name count below 3
- Post-trade cash below 5% stranded floor
- Orphans a theme/sector (no other positions)
- Creates liquidity hole (remaining positions lack ADV)

**FLAG is not a block**—it's a warning. Trader/PM decides whether to proceed.

---

## Integration with Pipeline

The book constraint gate is **orthogonal** to the existing scoring/backtest pipeline:

1. **Measurement layer** (`scripts/score.py`, `scripts/stock_signals.py`): Produces 6-pillar scores, VaR, regime, death cross signals → used by Research for BUY labels
2. **Policy layer** (`scripts/backtest/policy.py`, `scripts/recommendation.py`): Research labels (BUY/HOLD/SELL) vs Execute policy (`policy_hint`)
3. **Risk gate** (this module): Validates fund-level book constraints before ticket execution

```
signals → score → Research label (BUY/HOLD/SELL)
                        ↓
              policy_hint (Execute: FLAT/LONG)
                        ↓
              book_gate validation → ALLOW/BLOCK/FLAG
                        ↓
              Trader execution (if ALLOW)
```

### What Risk Does NOT Do

- ❌ Block HOLDs for VaR, death cross, Bear regime (those are research signals)
- ❌ Invent NAV, liquidity ADV, or correlation data
- ❌ Override CIO-approved holds
- ❌ Use 22-day daily VaR flatten walk as the operating model (retired July 2026)

### What Risk DOES Do

- ✅ Block BUY/ADD that breaks cash, name, sector/theme, liquidity, or purity limits
- ✅ Block BUY/ADD that exceeds option sleeve cap (20% for marked names)
- ✅ Check dollar weight for name cap (fractional shares supported)
- ✅ FLAG TRIM/SELL that strands the book
- ✅ Fail closed on missing data (NAV, asof, liquidity)
- ✅ Enforce theme purity (all positions must have tags)
- ✅ Validate factor cluster exposure (with correlation data for multi-name ADD)
- ✅ Do NOT count unmarked names toward option sleeve (no invented marks)

---

## Testing

Run the comprehensive test suite:

```bash
python -m pytest tests/test_risk_book_gate.py -v
# or
python tests/test_risk_book_gate.py
```

Tests cover:
- Missing NAV → BLOCK
- Missing asof → BLOCK
- CIO hold + death cross → ALLOW (not blocked by VaR)
- ADD over name/cash/sector/theme limits → BLOCK
- TRIM that strands names/theme → FLAG
- First-add correlation exception
- Factor cluster checks for multi-name ADD
- Liquidity enforcement (position < ADV/20)
- Theme purity enforcement
- Legacy veto object format

---

## Migration from VaR Flatten Model (PR #4)

If you have existing code using `vet_trade` or the 20/30/45 VaR ladder:

1. **Book constraint gate is the new default**: Use `check_book_constraints` for ticket validation
2. **Old VaR/CVaR/regime checks**: Keep as research signals (feed into `policy_hint`), but do NOT use them to veto HOLDs
3. **Concentration constants**: Reuse from `limits.py` (name 10%, sector 25%, cluster 35%, cash 10%, max 20 names)
4. **Fail-closed logic**: Preserved from old model (missing NAV → BLOCK, not invented)
5. **First-add exception**: Preserved (first BUY doesn't need correlation)

### Deprecation Path

The old `vet_trade` function (if it exists) should be:
- **Thin-wrapped** to call `check_book_constraints` for book validation
- **Deprecated** as the default gate (move VaR checks to research layer)
- **Kept for reference** in case old tests or journal rules still reference it

Do not keep the 22-day daily VaR flatten walk as the operating model going forward.

---

## File Structure

```
scripts/risk/
├── __init__.py          # Package exports
├── book_gate.py         # Main constraint validation logic
├── limits.py            # Concentration constants
└── README.md            # This file

tests/
└── test_risk_book_gate.py  # Comprehensive test suite
```

---

## Design Notes

### Why Not VaR for HOLDs?

- **VaR/CVaR/regime** are stock-level research signals about future volatility
- **Fund-level risk** cares about: Can we exit? Does this break the book? Are we too concentrated?
- **HOLDs** don't change the book—blocking them for overnight VaR would force unnecessary selling
- **CIO-approved** holds especially reflect a thesis decision, not a risk decision

### Why FLAG vs. BLOCK for TRIM/SELL?

- **BLOCK** is for constraint violations (breaking cash/concentration rules)
- **FLAG** is for operational warnings (stranding the book, orphaning themes)
- **Trader/PM** can override a FLAG if the exit is strategic (e.g., fund redemption, theme rotation)

### Why Fail Closed on Missing Data?

- **No live broker** in this paper-only system
- **Invented numbers** (NAV, ADV) create false confidence and bad fills
- **Fail-closed** forces upstream data quality (feed valid NAV, liquidity marks)

---

## Future Enhancements

Potential additions (not in scope for August 2026 release):

- [ ] Real-time liquidity marks from market data feed (replace static ADV)
- [ ] Dynamic theme taxonomy (auto-tag positions)
- [ ] Portfolio optimizer integration (suggest rebalance trades)
- [ ] Multi-day exit simulation for large positions
- [ ] Redemption/inflow handling (adjust cash floor)
- [ ] Cross-book risk aggregation (if managing multiple funds)

---

## Questions?

See the test suite (`tests/test_risk_book_gate.py`) for concrete examples.

Contact: Shahram (fund owner), Risk team (book constraints design)

**Remember**: Book constraints protect the **fund-level** portfolio structure. Stock-level signals (VaR, death cross) are research inputs, not risk vetoes.
