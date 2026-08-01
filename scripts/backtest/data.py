"""
Historical data loading and as-of replay support for backtesting.

Design goals:
- Price history is look-ahead safe via as-of slicing.
- OHLCV columns are always flat (Open/High/Low/Close/Volume) — no MultiIndex.
- Fundamentals from yfinance `info` are NOT point-in-time; replay uses a
  sanitized/empty info dict so live PE/ROE etc. do not leak into historical scores.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import yfinance as yf


OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _flatten_ohlcv(hist: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance MultiIndex / odd column layouts to flat OHLCV."""
    if hist is None or hist.empty:
        return pd.DataFrame(columns=OHLCV)

    h = hist.copy()
    if isinstance(h.columns, pd.MultiIndex):
        # Prefer level that contains OHLCV names
        level0 = {str(x) for x in h.columns.get_level_values(0)}
        if any(c in level0 for c in OHLCV):
            h.columns = h.columns.get_level_values(0)
        else:
            h.columns = h.columns.get_level_values(-1)

    # Deduplicate columns if flatten created duplicates
    if h.columns.duplicated().any():
        h = h.loc[:, ~h.columns.duplicated()]

    # Standardize names
    rename = {c: c.title() if isinstance(c, str) else c for c in h.columns}
    h = h.rename(columns=rename)

    # Keep OHLCV only when present
    cols = [c for c in OHLCV if c in h.columns]
    if not cols:
        # Last resort: first numeric cols
        num = h.select_dtypes(include="number")
        if num.shape[1] >= 4:
            num = num.iloc[:, :5]
            num.columns = OHLCV[: num.shape[1]]
            h = num
            cols = list(h.columns)
        else:
            raise ValueError(f"Cannot find OHLCV columns in history: {list(hist.columns)[:8]}")

    h = h[cols].copy()
    if not isinstance(h.index, pd.DatetimeIndex):
        h.index = pd.to_datetime(h.index)
    if h.index.tz is not None:
        h.index = h.index.tz_localize(None)
    h = h.sort_index()
    return h.dropna(how="all")


def load_historical_data(
    ticker: str,
    start: str | date,
    end: str | date | None = None,
    interval: str = "1d",
    lookback_days: int = 400,
) -> Dict[str, Any]:
    """
    Load historical OHLCV for backtesting.

    Downloads extra history *before* start for indicator warm-up (SMA200 etc.),
    but stores `start`/`end` so benchmarks use the test window only.
    """
    if isinstance(start, str):
        start = pd.to_datetime(start).date()
    if end is None:
        end = date.today()
    elif isinstance(end, str):
        end = pd.to_datetime(end).date()

    dl_start = start - timedelta(days=lookback_days)
    raw = yf.download(
        ticker,
        start=str(dl_start),
        end=str(end + timedelta(days=1)),
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raise ValueError(f"No data for {ticker} in range {start}→{end}")

    hist = _flatten_ohlcv(raw)
    # Keep warm-up + test window; do not drop pre-start (needed for indicators)
    hist = hist.loc[: pd.Timestamp(end)]
    if hist.empty:
        raise ValueError(f"No data for {ticker} after flatten/cutoff")

    # Point-in-time fundamentals are NOT available from yfinance info.
    # Use empty info so scoring does not inject *today's* PE/ROE into past dates.
    info: Dict[str, Any] = {}

    return {
        "ticker": ticker.upper(),
        "history": hist,
        "info": info,
        "start": str(start),
        "end": str(end),
        "lookback_days": lookback_days,
        "fundamentals_pit": False,  # explicit: live fundamentals disabled for replay
    }


def asof_snapshot(data: Dict[str, Any], asof: str | date) -> Dict[str, Any]:
    """Return price history strictly ≤ asof (look-ahead safe for prices)."""
    if isinstance(asof, str):
        asof_ts = pd.Timestamp(asof)
    else:
        asof_ts = pd.Timestamp(asof)

    hist = data["history"]
    if not isinstance(hist.index, pd.DatetimeIndex):
        hist.index = pd.to_datetime(hist.index)

    hist_asof = hist.loc[:asof_ts].copy()
    if hist_asof.empty:
        raise ValueError(f"No data as of {asof} for {data['ticker']}")

    snap = {
        "ticker": data["ticker"],
        "history": hist_asof,
        "info": {},  # never pass live info into historical scores
        "asof": str(asof_ts.date()),
        "start": data.get("start"),
        "end": data.get("end"),
        "fundamentals_pit": False,
    }
    return snap


def get_price_series(hist: pd.DataFrame, column: str = "Close") -> pd.Series:
    """Return a 1-D float Series for Open/High/Low/Close/Volume."""
    h = hist if list(hist.columns)[:1] == list(hist.columns)[:1] else hist
    if isinstance(h.columns, pd.MultiIndex):
        h = _flatten_ohlcv(h)
    if column not in h.columns:
        # case-insensitive fallback
        for c in h.columns:
            if str(c).lower() == column.lower():
                column = c
                break
        else:
            raise KeyError(f"Column {column} not in history. Available: {list(h.columns)}")
    s = h[column]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return pd.to_numeric(s, errors="coerce").dropna().astype(float)


def trading_days_in_range(hist: pd.DataFrame, start: str | date, end: str | date) -> pd.DatetimeIndex:
    """Trading days available in hist within [start, end] inclusive."""
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    idx = hist.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx)
    mask = (idx >= start_ts) & (idx <= end_ts)
    return idx[mask]


def next_trading_day(hist: pd.DataFrame, after: str | date | pd.Timestamp) -> Optional[pd.Timestamp]:
    """First bar strictly after `after`, or None."""
    after_ts = pd.Timestamp(after)
    idx = hist.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx)
    later = idx[idx > after_ts]
    if len(later) == 0:
        return None
    return later[0]


def bar_on(hist: pd.DataFrame, day: str | date | pd.Timestamp) -> Optional[pd.Series]:
    """OHLCV row for an exact trading day, or None."""
    day_ts = pd.Timestamp(day).normalize()
    idx = hist.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx)
    # match by date (ignore time)
    matches = hist.loc[idx.normalize() == day_ts]
    if matches.empty:
        # try exact
        if day_ts in hist.index:
            return hist.loc[day_ts]
        return None
    row = matches.iloc[-1]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return row
