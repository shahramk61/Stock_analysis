"""
Point-in-time returns matrix and pairwise correlation for Portfolio Manager.

Computes daily close-to-close returns using only OHLCV bars with index ≤ asof.
Aligns on the intersection of trading days (inner join).
Marks pairs unavailable when overlap is insufficient.

This is measurement-only. Does not invent correlations or pick entries.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# Minimum overlapping returns required to compute a correlation
# Below this threshold, mark the pair unavailable (not 0.0 or 1.0)
MIN_OVERLAP_RETURNS = 20


def compute_pit_returns_matrix(
    tickers: List[str],
    asof: str | datetime,
    hist_dict: Optional[Dict[str, pd.DataFrame]] = None,
    lookback_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Compute point-in-time returns matrix and pairwise correlations.

    Args:
        tickers: List of ticker symbols
        asof: As-of date (YYYY-MM-DD or datetime)
        hist_dict: Optional pre-loaded {ticker: hist_df} where hist is OHLCV
                   If not provided, caller must pre-load (no live fetch here)
        lookback_days: Optional lookback window (trading days) from asof
                       If None, uses all available history ≤ asof

    Returns:
        Dictionary with:
        - returns_matrix: DataFrame of daily returns (dates × tickers)
        - corr_matrix: Pairwise correlation matrix (tickers × tickers)
        - availability: Dict tracking which pairs were computed vs unavailable
        - asof: As-of date used
        - tickers: List of tickers processed
        - overlap_counts: Dict of overlapping return counts per pair
        - min_overlap_threshold: Minimum overlap required
    """
    if isinstance(asof, str):
        asof_ts = pd.Timestamp(asof)
    else:
        asof_ts = pd.Timestamp(asof)

    asof_str = str(asof_ts.date())

    # Validate inputs
    if not tickers or len(tickers) < 1:
        return {
            "error": "Need at least 1 ticker for returns matrix",
            "asof": asof_str,
            "tickers": tickers,
        }

    if hist_dict is None:
        return {
            "error": "hist_dict required. Pre-load OHLCV history for each ticker.",
            "asof": asof_str,
            "tickers": tickers,
        }

    # Extract returns for each ticker (asof-sliced)
    returns_series = {}
    availability = {}

    for ticker in tickers:
        hist = hist_dict.get(ticker)
        if hist is None or hist.empty:
            availability[ticker] = "unavailable (no hist)"
            continue

        # Ensure hist is properly indexed
        if not isinstance(hist.index, pd.DatetimeIndex):
            hist.index = pd.to_datetime(hist.index)

        # Slice to asof
        hist_asof = hist.loc[:asof_ts].copy()
        if hist_asof.empty:
            availability[ticker] = "unavailable (no bars <= asof)"
            continue

        # Apply lookback if specified
        if lookback_days is not None and len(hist_asof) > lookback_days:
            hist_asof = hist_asof.iloc[-lookback_days:]

        # Compute daily close-to-close returns
        try:
            closes = hist_asof["Close"]
            returns = closes.pct_change().dropna()
            if len(returns) == 0:
                availability[ticker] = "unavailable (no returns computed)"
                continue
            returns_series[ticker] = returns
            availability[ticker] = "computed"
        except Exception:
            availability[ticker] = "unavailable (computation failed)"
            continue

    # Check if we have enough tickers with data
    if len(returns_series) < 1:
        return {
            "error": "No tickers with valid returns data ≤ asof",
            "asof": asof_str,
            "tickers": tickers,
            "availability": availability,
        }

    # Align returns on intersection of trading days (inner join)
    returns_df = pd.DataFrame(returns_series)
    # Inner join: only dates where all tickers have returns
    # But this is too strict if we want to compute pairwise for subsets
    # Instead, keep all dates and let pairwise handle NaN

    # Actually, let's align per pair for pairwise correlation
    # Build returns matrix with all available dates (outer join)
    returns_df = pd.DataFrame(returns_series)

    # Compute pairwise correlations
    corr_matrix = pd.DataFrame(
        index=returns_df.columns,
        columns=returns_df.columns,
        dtype=float,
    )
    overlap_counts = {}
    pair_availability = {}

    for ticker1 in returns_df.columns:
        for ticker2 in returns_df.columns:
            pair_key = f"{ticker1}_{ticker2}"

            if ticker1 == ticker2:
                # Self-correlation is always 1.0 (if ticker has data)
                corr_matrix.loc[ticker1, ticker2] = 1.0
                pair_availability[pair_key] = "computed (self)"
                overlap_counts[pair_key] = len(returns_df[ticker1].dropna())
                continue

            # Get overlapping returns (both non-NaN)
            pair_returns = returns_df[[ticker1, ticker2]].dropna()
            overlap_count = len(pair_returns)
            overlap_counts[pair_key] = overlap_count

            if overlap_count < MIN_OVERLAP_RETURNS:
                # Insufficient overlap: mark unavailable
                corr_matrix.loc[ticker1, ticker2] = np.nan
                pair_availability[pair_key] = (
                    f"unavailable (overlap={overlap_count} < {MIN_OVERLAP_RETURNS})"
                )
            else:
                # Compute correlation from overlapping returns
                try:
                    corr_val = pair_returns[ticker1].corr(pair_returns[ticker2])
                    if pd.isna(corr_val):
                        # Correlation undefined (e.g., zero variance)
                        corr_matrix.loc[ticker1, ticker2] = np.nan
                        pair_availability[pair_key] = "unavailable (corr undefined)"
                    else:
                        corr_matrix.loc[ticker1, ticker2] = corr_val
                        pair_availability[pair_key] = "computed"
                except Exception:
                    corr_matrix.loc[ticker1, ticker2] = np.nan
                    pair_availability[pair_key] = "unavailable (computation failed)"

    return {
        "asof": asof_str,
        "tickers": list(returns_df.columns),
        "returns_matrix": returns_df,
        "corr_matrix": corr_matrix,
        "availability": availability,
        "pair_availability": pair_availability,
        "overlap_counts": overlap_counts,
        "min_overlap_threshold": MIN_OVERLAP_RETURNS,
    }


def compute_pit_pairwise_corr(
    ticker1: str,
    ticker2: str,
    asof: str | datetime,
    hist_dict: Dict[str, pd.DataFrame],
    lookback_days: Optional[int] = None,
) -> Tuple[Optional[float], str]:
    """
    Compute point-in-time pairwise correlation between two tickers.

    Args:
        ticker1: First ticker
        ticker2: Second ticker
        asof: As-of date
        hist_dict: Pre-loaded {ticker: hist_df}
        lookback_days: Optional lookback window

    Returns:
        (correlation_value, status)
        correlation_value is None if unavailable
        status is "computed" or "unavailable (reason)"
    """
    result = compute_pit_returns_matrix(
        tickers=[ticker1, ticker2],
        asof=asof,
        hist_dict=hist_dict,
        lookback_days=lookback_days,
    )

    if "error" in result:
        return None, f"unavailable ({result['error']})"

    pair_key = f"{ticker1}_{ticker2}"
    pair_avail = result["pair_availability"].get(pair_key, "unavailable")

    if pair_avail == "computed":
        corr_val = result["corr_matrix"].loc[ticker1, ticker2]
        return float(corr_val), "computed"
    else:
        return None, pair_avail
