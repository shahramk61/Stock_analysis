# Quant Fund Tools

**Ownership**: Quant owns whether the numbers are real.

This package provides Quant's fund tools for Shahram's paper thematic fund:

1. **Asof marks on every measurement** — Every score, conviction, ticket state, and model output carries asof (date) and source
2. **CIO conviction/score tracker** — Read-only ledger the CIO can consume
3. **Honest five-year model support** — Unavailable if cannot compute, no invented revenues
4. **Walk-forward of PM tickets** — Replay buy/add/trim/sell/rebalance with attribution

## Philosophy

- **Asof-safe**: Every measurement is marked with the date it was computed and the data source
- **Conservative**: If a field cannot be computed from asof-safe inputs, it is marked unavailable (not fabricated)
- **Measurement-only**: Quant does NOT pick themes, does NOT issue tickets, does NOT invent conviction
- **PIT integrity**: No live yfinance fundamentals leaking into historical replay, no placeholder VaR/CVaR values

## What the CIO Can Read

### 1. CIO Tracker (Read-Only Ledger)

The CIO tracker provides a time series of asof-safe measurements for each name:

**Available fields per name:**
- `ticker`: Stock ticker symbol
- `asof`: As-of date (data available <= asof)
- `theme`: Theme tag (supplied by others, never invented by Quant)
- `overall_score`: Weighted overall score (0-100 scale)
- `pillar_scores`: Dictionary of pillar scores (fundamentals, technicals, valuation, sentiment, esg_quality, risk)
- `last_print`: Last Close price <= asof
- `last_print_date`: Date of last_print
- `last_print_source`: "hist_close_asof" (never a live peek)
- `var_95`: 95% VaR (if computed from asof-sliced returns, else None)
- `cvar_95`: 95% CVaR (if computed from asof-sliced returns, else None)
- `availability`: Dictionary tracking which fields were computed vs unavailable
- `conviction`: Derived from score bands (High>=75, Medium>=60, Low<60) or None if score unavailable
- `conviction_rule`: Rule used to derive conviction

**CLI usage:**

```bash
# Latest tracker state at a specific date
python -m scripts.quant.fund.cli tracker-latest \
  --tickers AAPL,MSFT,GOOGL \
  --asof 2023-12-31 \
  --output tracker_latest.json

# Tracker time series over a date range
python -m scripts.quant.fund.cli tracker-series \
  --tickers AAPL,MSFT,GOOGL \
  --start 2023-01-01 \
  --end 2023-12-31 \
  --rebalance-days 20 \
  --output tracker_series.json
```

**API usage:**

```python
from scripts.quant.fund import get_latest_tracker_state, get_tracker_time_series
from scripts.backtest.data import load_historical_data

# Load historical data
hist_dict = {}
for ticker in ["AAPL", "MSFT", "GOOGL"]:
    data = load_historical_data(ticker, start="2023-01-01", end="2023-12-31")
    hist_dict[ticker] = data["history"]

# Latest state
tracker = get_latest_tracker_state(
    tickers=["AAPL", "MSFT", "GOOGL"],
    asof="2023-12-31",
    hist_dict=hist_dict,
)

# Time series
tracker_series = get_tracker_time_series(
    tickers=["AAPL", "MSFT", "GOOGL"],
    start="2023-01-01",
    end="2023-12-31",
    hist_dict=hist_dict,
    rebalance_days=20,
)

# Save to file
tracker.save("tracker.json")
```

### 2. Five-Year Model

Five-year projection model (HONEST: only from asof-safe PIT fundamentals).

**Available fields:**
- `is_available`: True if model could compute, False if unavailable
- `unavailable_reason`: Why model is unavailable (e.g., "No PIT fundamental store")
- `projected_revenues`: List of 5 annual revenue projections (if available)
- `projected_earnings`: List of 5 annual earnings projections (stub: None in v1)
- `projected_fcf`: List of 5 annual FCF projections (stub: None in v1)
- `terminal_value`: Terminal value (stub: None in v1)
- `fair_value`: Fair value estimate (stub: None in v1)

**CLI usage:**

```bash
# Evaluate five-year model (with PIT revenues)
python -m scripts.quant.fund.cli five-year-model \
  --ticker AAPL \
  --asof 2023-12-31 \
  --revenues "100,110,121,133,146"
```

**API usage:**

```python
from scripts.quant.fund import evaluate_five_year_model
from scripts.quant.fund.five_year_model import create_pit_fundamentals_stub

# Create PIT fundamentals stub (for testing)
pit_fundamentals = create_pit_fundamentals_stub(
    ticker="AAPL",
    asof="2023-12-31",
    historical_revenues=[100, 110, 121, 133, 146],
)

# Evaluate model
result = evaluate_five_year_model(
    ticker="AAPL",
    asof="2023-12-31",
    pit_fundamentals=pit_fundamentals,
)

if result.is_available:
    print(result.projected_revenues)
else:
    print(result.unavailable_reason)
```

### 3. PM Ticket Replay

Walk-forward replay of PM-issued tickets: buy / add / trim / sell / rebalance.

**Input (PM provides):**
- List of tickets with: date, ticker, action, qty/weight, optional limit

**Output:**
- `fills`: List of ticket fills (filled=True/False, fill_price, fill_date, unfilled_reason)
- `book_snapshots`: List of paper book states after each ticket
- `attributions`: List of realized PnL after asof (for sells/trims)
- `final_book`: Final paper book state (positions, cash, weights)

**CLI usage:**

Create a JSON file with PM tickets:

```json
[
  {"date": "2023-01-05", "ticker": "AAPL", "action": "buy", "qty": 10},
  {"date": "2023-03-15", "ticker": "MSFT", "action": "buy", "qty": 5},
  {"date": "2023-06-20", "ticker": "AAPL", "action": "trim", "qty": 5},
  {"date": "2023-12-15", "ticker": "AAPL", "action": "sell", "qty": 5}
]
```

Then replay:

```bash
python -m scripts.quant.fund.cli replay-tickets \
  --tickets-file pm_tickets.json \
  --starting-capital 3000 \
  --output replay_result.json
```

**API usage:**

```python
from scripts.quant.fund import replay_pm_tickets, Ticket, TicketAction
from scripts.backtest.data import load_historical_data
from datetime import date

# Create tickets
tickets = [
    Ticket(date=date(2023, 1, 5), ticker="AAPL", action=TicketAction.BUY, qty=10),
    Ticket(date=date(2023, 6, 20), ticker="AAPL", action=TicketAction.SELL, qty=10),
]

# Load historical data
hist_aapl = load_historical_data("AAPL", start="2023-01-01", end="2023-12-31")

# Replay tickets
result = replay_pm_tickets(
    tickets=tickets,
    hist_dict={"AAPL": hist_aapl["history"]},
    starting_capital=3000.0,
)

# Check fills
for fill in result.fills:
    if fill.filled:
        print(f"Filled: {fill.ticket.action} {fill.fill_qty} @ {fill.fill_price} on {fill.fill_date}")
    else:
        print(f"Unfilled: {fill.unfilled_reason}")

# Check final book
print(f"Final cash: {result.final_book.cash}")
for ticker, pos in result.final_book.positions.items():
    print(f"{ticker}: {pos.qty} shares @ avg cost {pos.avg_cost}")
```

## What Is Unavailable

### In Current Implementation (v1):

1. **Five-year model projections** — Unavailable unless PIT fundamental store exists:
   - No PIT revenue store → model returns `is_available=False`
   - No fabricated revenues, no live yfinance financials
   - Projected earnings, FCF, terminal value, fair value: stub (None) in v1

2. **Fundamental pillar scores** — Baseline values (no PIT fundamental store):
   - Fundamentals pillar: 60.0 (baseline, no Altman/Piotroski/quality available)
   - Valuation pillar: 60.0 (baseline, no DCF available)
   - Sentiment pillar: 65.0 (baseline, no earnings surprise/FinBERT available)
   - ESG/Quality pillar: 70.0 (baseline, no distress/Piotroski available)

3. **MC Risk (VaR/CVaR)** — Only available if sufficient hist for Monte Carlo simulation:
   - If hist is insufficient (< ~60 days of returns), `var_95` and `cvar_95` are None
   - Never 20.0/28.0 placeholders (those are detected and marked unavailable)

4. **Attribution (realized PnL)** — Simplified in v1:
   - Lot tracking not implemented (FIFO/LIFO)
   - Realized PnL computed for sells/trims but marked as stub

### Quant Does NOT:

1. **Pick themes** — Theme tags are supplied by others, never invented by Quant
2. **Issue tickets** — PM provides tickets, Quant replays them
3. **Invent conviction** — Conviction is derived from score bands or marked unavailable
4. **Invent prices** — If no bar available on ticket date, ticket is unfilled (no invented price)
5. **Emit BUY/SELL recommendations** — Quant measures, does not recommend

## Design Rules

1. **Asof marks on everything**: Every measurement carries asof (date) and source
2. **No fabricated numbers**: If cannot compute from asof-safe data, mark unavailable
3. **PIT integrity**: No live yfinance fundamentals, no placeholder values presented as real
4. **Walk-forward safe**: Score at date T is invariant to bars after T
5. **Forecasts off**: Multi-horizon forecasts are research-only, default off

## Future Work

1. **Point-in-time fundamental store**: Build historical snapshot database for quarterly financials keyed by (ticker, report_date). Once available, five-year model can compute real projections.

2. **Lot tracking**: Implement FIFO/LIFO for accurate realized PnL attribution.

3. **Full five-year model**: Expand model to compute projected earnings, FCF, terminal value, fair value from PIT fundamentals.

4. **Theme attribution**: Track theme-level performance (supplied themes only, never invented).

## Testing

Run fund tool tests:

```bash
pytest tests/test_fund_asof_marks.py
pytest tests/test_fund_five_year_model.py
pytest tests/test_fund_ticket_replay.py
pytest tests/test_fund_tracker.py
```

These tests prove:
- Asof marks are immutable and carry date + source
- Five-year model returns unavailable when no PIT revenues (never fabricated)
- Ticket walk-forward: buy then sell produces computed PnL
- Ticket on date with no bar is unfilled (no invented price)
- Future bars after asof do not change fills at T
- Tracker entries have asof marks, mutating future bar does not change asof-T score

All tests use synthetic data (no network).

## Integration with Existing Quant Tools

The fund tools integrate with existing Quant measurement layer:

- **`scripts.quant.pit_score.compute_pit_score()`** — Used by tracker to compute per-name scores
- **`scripts.quant.walkforward.run_walkforward()`** — Used by tracker time series
- **`scripts.quant.no_lookahead.lookahead_guard()`** — Runtime guard enabled during tracker computation

The existing July PIT name scores (`scripts/quant/pit_score.py`, `scripts/quant/walkforward.py`) stay as tools and are not broken.

## License

Same as parent repository.

## Questions?

This is Quant's fund measurement layer. If the numbers don't make sense, that's a Quant problem. If themes or ticket actions are wrong, that's a PM problem. Keep them separate.
