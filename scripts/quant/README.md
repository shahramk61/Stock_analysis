# Quant Measurement Layer

**Ownership**: Quant owns whether the numbers are real.

This package provides Quant's first measurement layer for Stock Analysis:
1. **Point-in-time scores**: Compute pillar scores using only data available at a specific historical date
2. **Walk-forward replay**: Step through time computing scores at each rebalance point
3. **Hard no-lookahead check**: Runtime guards and static audit to detect future information leaks

## Philosophy

- **Falsifiable**: Every number can be traced to asof-sliced OHLCV data
- **Conservative**: If a field cannot be computed from asof-safe inputs, it is marked unavailable (not fabricated)
- **Measurement-only**: No trade recommendations, no entry decisions, no policy changes
- **Forecasts off by default**: Multi-horizon ML forecasts are research-only and opt-in

## What This Proves

### ✓ Point-in-Time Scoring Works
- `compute_pit_score()` uses only OHLCV bars with `index <= asof`
- Runtime guard fails hard if live yfinance fundamentals are accessed during replay
- Availability ledger tracks which fields were computed vs unavailable vs leaked

### ✓ Walk-Forward Replay is Leak-Free (for price signals)
- `run_walkforward()` steps asof forward, computing PIT scores at each rebalance
- Asof dates are strictly increasing
- Score at date T is invariant to bars after T (proven by tests)
- Realized returns are attached AFTER asof for outcome measurement (not fed back into scores)

### ✓ Leaks Are Detected
- Runtime guard: catches live `Ticker.info`, `.financials`, `.balance_sheet`, etc. during guarded execution
- Static audit: scans code for known leaking helpers (Altman, Piotroski, quality, earnings, info dict accesses)
- Tests prove: if a helper fetches live yfinance fundamentals, the guard FAILS

## What Is Still Leaking

### In the Inherited `scripts/` Path (NOT in Quant tools):

1. **`scripts/score.py` fundamental helpers**:
   - `calculate_altman_beneish(ticker)` (line 35) — NO hist/asof passed
   - `get_earnings_surprise(ticker)` (line 36) — NO hist/asof passed
   - `calculate_piotroski_f_score(ticker)` (line 39) — NO hist/asof passed
   - `get_quality_accruals_gross_profit(ticker)` (line 45) — NO hist/asof passed
   - `get_finbert_sentiment(ticker)` (line 66) — fetches live news
   - `info.get('returnOnEquity')`, `info.get('revenueGrowth')` (lines 163-164) — live info dict
   - `calculate_dcf(data)` (line 38) — uses live `data['info']` for interest expense, tax rate, shares

2. **`scripts/stock_signals.py`**:
   - `calculate_altman_beneish()` (lines 66-91) — fetches live balance sheet / income statement
   - `get_earnings_surprise()` (lines 93-107) — fetches live earnings dates
   - `calculate_piotroski_f_score()` (lines 134-159) — fetches live financials
   - `get_quality_accruals_gross_profit()` (lines 266-297) — fetches live financials
   - `get_finbert_sentiment()` (lines 925-955) — fetches live news
   - `get_share_turnover()` (line 392) — calls `stock.info` for shares outstanding

3. **`scripts/dcf.py`**:
   - Uses `data.get('info', {})` for interest expense (line 30), tax rate (line 37), shares (lines 97-98)

4. **`tests/test_no_lookahead.py`**:
   - Line 54: `or True` tautology — test never fails
   - Only checks OHLCV slice max date, does NOT test fundamental leaks

### In Quant Tools:

**None.** The Quant PIT scorer and walk-forward replay:
- Use ONLY asof-sliced OHLCV
- Mark fundamental fields as unavailable (no PIT fundamental store exists)
- Never fetch live yfinance fundamentals
- Default forecasts OFF
- Fail hard if guarded execution detects a leak

## Installation

No extra dependencies required. Uses existing repo packages (pandas, numpy, yfinance, etc.).

## Usage

### 1. Point-in-Time Score

```bash
python -m scripts.quant pit-score AAPL --asof 2023-06-01
```

Computes the score at June 1, 2023 using only data available on or before that date.

Output includes:
- Overall and pillar scores
- Availability ledger (which fields were computed vs unavailable)
- Optional `--json` for full structured output

### 2. Walk-Forward Replay

```bash
python -m scripts.quant walk-forward AAPL --start 2023-01-01 --end 2023-12-31
```

Steps through 2023, computing PIT scores every 20 trading days (configurable with `--rebalance-days`).

Output includes:
- Summary statistics (avg/min/max scores)
- Per-step scores and availability
- Realized returns attached for falsification (5d and 20d forward by default)

### 3. No-Lookahead Audit

```bash
python -m scripts.quant audit
```

Scans `scripts/` for known leaking patterns:
- Fundamental helpers called without hist/asof
- yfinance fundamental attribute accesses
- `info.get()` / `info[...]` patterns (live fundamental data)

Reports each detected leak with file, line, and context.

## API Usage

```python
from scripts.quant import compute_pit_score, run_walkforward
from scripts.backtest.data import load_historical_data

# Load history
data = load_historical_data("AAPL", start="2023-01-01", end="2023-12-31")
hist = data["history"]

# Point-in-time score
score = compute_pit_score(
    ticker="AAPL",
    asof="2023-06-01",
    hist=hist,
    profile="Balanced",
    use_forecasts=False,
)
print(score["overall_score"])
print(score["availability"])

# Walk-forward
replay = run_walkforward(
    ticker="AAPL",
    start="2023-01-01",
    end="2023-12-31",
    hist=hist,
    rebalance_days=20,
)
print(replay["summary"])
```

## Testing

Run Quant tests:

```bash
pytest tests/test_quant_pit_score.py
pytest tests/test_quant_walkforward.py
pytest tests/test_quant_no_lookahead.py
```

These tests prove:
- PIT score at date T never sees bars after T (mutation tests)
- Walk-forward asof dates are strictly increasing
- Mutating future bars does not change past scores
- Live fundamental access during guarded replay FAILS
- Audit detects known leaking helpers in scripts/

## Design Constraints

1. **No fabricated numbers**: If a field cannot be computed from asof-safe data, mark it unavailable. Never fill with live yfinance or a made-up default presented as real.

2. **Forecasts off by default**: `use_forecasts=False`. Multi-horizon LSTM/Chronos/Path C are research-only.

3. **Measurement-only**: This package does NOT emit trade recommendations, choose entries, or modify policy. That is the desk's job.

4. **Reuse where safe**: Price/vol/liquidity signals in `scripts/stock_signals.py` that accept hist=/asof= are reused. Fundamental helpers that do NOT accept hist=/asof= are withheld.

5. **Runtime guards are opt-in but recommended**: Call `patch_yfinance_guards()` before replay to catch leaks. The CLI does this automatically.

## Future Work

1. **Point-in-time fundamental store**: Build a historical snapshot database for quarterly financials (balance sheet, income statement, cashflow) keyed by (ticker, report_date). Once available, Quant PIT scorer can compute Altman, Piotroski, quality, DCF at any asof without leaking.

2. **Deprecate leaking helpers**: Replace `calculate_altman_beneish()` etc. in `scripts/` with PIT-aware versions that accept hist=/asof= or a fundamental store handle.

3. **Expand walk-forward**: Add strategy simulation (signal → position → return), but keep it separate from measurement. Measurement proves the scores; strategy tests the desk's policy.

## License

Same as parent repository.

## Questions?

This is Quant's measurement layer. If the numbers don't make sense, that's a Quant problem. If the entry policy is wrong, that's a desk problem. Keep them separate.
