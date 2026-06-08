"""
Historical data loading and as-of replay support for backtesting.

Phase 1 focus: load price history + fundamentals with explicit date cutoffs.
Support pre-fetch + caching for efficiency during walk-forward loops.
Provide snapshots so signal functions can run "as of" a past date (avoiding look-ahead).

See approved plan for details. Start simple (prices first), then fundamentals.
"""

from __future__ import annotations
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import yfinance as yf

# TODO (Phase 1): Implement proper as-of loading that respects reporting lags for financials/earnings.
# For MVP: focus on price history (easy) + basic info snapshot. Fundamentals can use latest available as-of.

def load_historical_data(
    ticker: str,
    start: str | date,
    end: str | date | None = None,
    period: str | None = None,
    interval: str = "1d",
    prepost: bool = False,
) -> Dict[str, Any]:
    """
    Load historical price data + basic info for a ticker over a date range.
    Returns a dict similar to fetch_stock_data but bounded.
    This is the entry point for backtest data prep.

    For now wraps yfinance with explicit dates. Later: cache to parquet, handle adjustments, etc.
    """
    if isinstance(start, str):
        start = pd.to_datetime(start).date()
    if end is None:
        end = date.today()
    elif isinstance(end, str):
        end = pd.to_datetime(end).date()

    # yf uses strings or pd.Timestamp
    hist = yf.download(
        ticker,
        start=str(start - timedelta(days=30)),  # buffer for indicators
        end=str(end + timedelta(days=1)),
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if hist.empty:
        raise ValueError(f"No data for {ticker} in range")

    hist = hist.loc[:str(end)]  # strict cutoff
    info = {}  # TODO: yf info is "current"; for true point-in-time we need other sources later
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
    except Exception:
        pass

    return {
        "ticker": ticker.upper(),
        "history": hist,
        "info": info,
        "start": str(start),
        "end": str(end),
        # TODO: add 'fundamentals_asof': snapshot of statements as of end date
    }


def asof_snapshot(data: Dict[str, Any], asof: str | date) -> Dict[str, Any]:
    """
    Return a view of the data 'as of' a specific past date.
    Used to feed signals/score/quant without look-ahead.

    For prices: slice history up to asof.
    For now, info/fundamentals are latest (limitation noted in plan).
    """
    if isinstance(asof, str):
        asof = pd.to_datetime(asof).date()

    hist = data["history"]
    if not isinstance(hist.index, pd.DatetimeIndex):
        hist.index = pd.to_datetime(hist.index)

    hist_asof = hist.loc[:str(asof)].copy()
    if hist_asof.empty:
        raise ValueError(f"No data as of {asof} for {data['ticker']}")

    snap = dict(data)  # shallow
    snap["history"] = hist_asof
    snap["asof"] = str(asof)
    # TODO: fundamentals slice / point-in-time statements
    return snap


def get_price_series(hist: pd.DataFrame, column: str = "Close") -> pd.Series:
    """Convenience for backtest loops."""
    if column in hist:
        return hist[column].dropna()
    # yf download sometimes uses different casing / multiindex
    if (column,) in hist.columns:
        return hist[(column,)].dropna()
    raise KeyError(f"Column {column} not in history. Available: {list(hist.columns)[:5]}...")


# TODO (later phases): add cache_to_parquet, load_from_cache, fundamentals_asof using earnings dates etc.
# TODO: support multiple tickers efficiently.
