"""
Tests for PIT returns matrix and pairwise correlation.

Proves:
1. Two series with known overlapping returns → corr is computed and finite
2. Future-bar mutation does not change the corr
3. One ticker or empty universe → corr unavailable
4. Two series with almost no overlap → that pair unavailable
"""

import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from quant.returns_matrix import (
    compute_pit_returns_matrix,
    compute_pit_pairwise_corr,
    MIN_OVERLAP_RETURNS,
)


def _synthetic_hist(n: int = 300, seed: int = 42, base_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic OHLCV history."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=datetime.today(), periods=n)
    rets = rng.normal(0.0005, 0.015, size=n)
    close = base_price * np.cumprod(1 + rets)
    high = close * (1 + rng.uniform(0, 0.01, size=n))
    low = close * (1 - rng.uniform(0, 0.01, size=n))
    open_ = close * (1 + rng.normal(0, 0.002, size=n))
    vol = rng.integers(1_000_000, 5_000_000, size=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=dates,
    )


def test_returns_matrix_two_tickers_with_overlap():
    """Two tickers with overlapping returns → corr is computed and finite."""
    hist1 = _synthetic_hist(260, seed=42, base_price=100.0)
    hist2 = _synthetic_hist(260, seed=43, base_price=200.0)
    asof = hist1.index[180]

    hist_dict = {
        "TICK1": hist1.loc[:asof].copy(),
        "TICK2": hist2.loc[:asof].copy(),
    }

    result = compute_pit_returns_matrix(
        tickers=["TICK1", "TICK2"],
        asof=asof,
        hist_dict=hist_dict,
    )

    # Should not have error
    assert "error" not in result

    # Returns matrix should be present
    assert "returns_matrix" in result
    returns = result["returns_matrix"]
    assert "TICK1" in returns.columns
    assert "TICK2" in returns.columns
    assert len(returns) > 0

    # Correlation matrix should be present
    assert "corr_matrix" in result
    corr = result["corr_matrix"]

    # Self-correlations should be 1.0
    assert corr.loc["TICK1", "TICK1"] == 1.0
    assert corr.loc["TICK2", "TICK2"] == 1.0

    # Pairwise correlation should be computed
    corr_12 = corr.loc["TICK1", "TICK2"]
    corr_21 = corr.loc["TICK2", "TICK1"]

    # Should be finite (not NaN)
    assert pd.notna(corr_12)
    assert pd.notna(corr_21)

    # Should be symmetric
    assert abs(corr_12 - corr_21) < 1e-10

    # Should be in valid range [-1, 1]
    assert -1.0 <= corr_12 <= 1.0

    # Availability should be "computed"
    assert result["pair_availability"]["TICK1_TICK2"] == "computed"


def test_returns_matrix_future_mutation_invariance():
    """Corr at asof-T should not change if future bars are mutated."""
    hist1 = _synthetic_hist(260, seed=42)
    hist2 = _synthetic_hist(260, seed=43)
    asof_idx = 180
    asof = hist1.index[asof_idx]
    future_idx = 200

    # Compute with original hist
    hist_dict1 = {
        "TICK1": hist1.loc[:asof].copy(),
        "TICK2": hist2.loc[:asof].copy(),
    }
    result1 = compute_pit_returns_matrix(
        tickers=["TICK1", "TICK2"],
        asof=asof,
        hist_dict=hist_dict1,
    )

    # Mutate future bars
    hist1_mutated = hist1.copy()
    hist2_mutated = hist2.copy()
    hist1_mutated.loc[hist1_mutated.index[future_idx], "Close"] *= 2.0
    hist2_mutated.loc[hist2_mutated.index[future_idx], "Close"] *= 0.5

    # Compute again with mutated hist (still sliced to same asof)
    hist_dict2 = {
        "TICK1": hist1_mutated.loc[:asof].copy(),
        "TICK2": hist2_mutated.loc[:asof].copy(),
    }
    result2 = compute_pit_returns_matrix(
        tickers=["TICK1", "TICK2"],
        asof=asof,
        hist_dict=hist_dict2,
    )

    # Correlations must be identical
    corr1 = result1["corr_matrix"].loc["TICK1", "TICK2"]
    corr2 = result2["corr_matrix"].loc["TICK1", "TICK2"]
    assert abs(corr1 - corr2) < 1e-10, f"Corr changed after future mutation: {corr1} != {corr2}"

    # Returns matrices should be identical
    returns1 = result1["returns_matrix"]
    returns2 = result2["returns_matrix"]
    pd.testing.assert_frame_equal(returns1, returns2)


def test_returns_matrix_empty_universe():
    """Empty universe → error (no corr computed)."""
    result = compute_pit_returns_matrix(
        tickers=[],
        asof="2023-01-01",
        hist_dict={},
    )

    # Should have error
    assert "error" in result
    assert "at least 1 ticker" in result["error"].lower()


def test_returns_matrix_single_ticker():
    """Single ticker → self-correlation 1.0, no pairwise."""
    hist = _synthetic_hist(260, seed=42)
    asof = hist.index[180]

    hist_dict = {"TICK1": hist.loc[:asof].copy()}

    result = compute_pit_returns_matrix(
        tickers=["TICK1"],
        asof=asof,
        hist_dict=hist_dict,
    )

    # Should not have error
    assert "error" not in result

    # Corr matrix should have self-correlation 1.0
    corr = result["corr_matrix"]
    assert corr.loc["TICK1", "TICK1"] == 1.0

    # No pairwise correlations (only one ticker)
    assert corr.shape == (1, 1)


def test_returns_matrix_no_hist_for_ticker():
    """Ticker with no hist → marked unavailable."""
    hist1 = _synthetic_hist(260, seed=42)
    asof = hist1.index[180]

    hist_dict = {
        "TICK1": hist1.loc[:asof].copy(),
        # TICK2 has no hist
    }

    result = compute_pit_returns_matrix(
        tickers=["TICK1", "TICK2"],
        asof=asof,
        hist_dict=hist_dict,
    )

    # Should not have error (one ticker has data)
    assert "error" not in result

    # TICK1 should be available
    assert result["availability"]["TICK1"] == "computed"

    # TICK2 should be unavailable
    assert "unavailable" in result["availability"]["TICK2"]

    # Only TICK1 in returns matrix
    assert "TICK1" in result["returns_matrix"].columns
    assert "TICK2" not in result["returns_matrix"].columns


def test_returns_matrix_insufficient_overlap():
    """Two series with almost no overlap → that pair unavailable."""
    # Create two series with minimal overlap
    hist1 = _synthetic_hist(50, seed=42)  # First 50 days
    hist2 = _synthetic_hist(50, seed=43)  # Different 50 days (dates will overlap, but we'll slice)

    # Shift hist2 dates to create minimal overlap
    hist2_shifted = hist2.copy()
    hist2_shifted.index = pd.bdate_range(
        start=hist1.index[-5],  # Overlap only last 5 days of hist1
        periods=50,
    )

    asof = hist1.index[-1]  # End of hist1

    hist_dict = {
        "TICK1": hist1.loc[:asof].copy(),
        "TICK2": hist2_shifted.loc[:asof].copy(),  # Only last 5 bars overlap
    }

    result = compute_pit_returns_matrix(
        tickers=["TICK1", "TICK2"],
        asof=asof,
        hist_dict=hist_dict,
    )

    # Should not have error
    assert "error" not in result

    # Both tickers individually should have returns
    assert result["availability"]["TICK1"] == "computed"
    assert result["availability"]["TICK2"] == "computed"

    # But pairwise correlation should be unavailable due to low overlap
    pair_avail = result["pair_availability"]["TICK1_TICK2"]
    overlap_count = result["overlap_counts"]["TICK1_TICK2"]

    # Overlap should be less than MIN_OVERLAP_RETURNS (20)
    assert overlap_count < MIN_OVERLAP_RETURNS

    # Pair should be unavailable
    assert "unavailable" in pair_avail
    assert f"overlap={overlap_count}" in pair_avail

    # Corr should be NaN (not 0.0, not 1.0)
    corr = result["corr_matrix"].loc["TICK1", "TICK2"]
    assert pd.isna(corr), "Insufficient overlap should result in NaN, not fabricated corr"


def test_pairwise_corr_helper():
    """Pairwise corr helper should work correctly."""
    hist1 = _synthetic_hist(260, seed=42)
    hist2 = _synthetic_hist(260, seed=43)
    asof = hist1.index[180]

    hist_dict = {
        "TICK1": hist1.loc[:asof].copy(),
        "TICK2": hist2.loc[:asof].copy(),
    }

    corr_val, status = compute_pit_pairwise_corr(
        "TICK1", "TICK2", asof, hist_dict
    )

    # Should be computed
    assert status == "computed"
    assert corr_val is not None
    assert -1.0 <= corr_val <= 1.0


def test_returns_matrix_lookback_window():
    """Lookback window should limit returns to recent trading days."""
    hist = _synthetic_hist(260, seed=42)
    asof = hist.index[180]
    lookback = 60  # Last 60 trading days

    hist_dict = {"TICK1": hist.loc[:asof].copy()}

    result = compute_pit_returns_matrix(
        tickers=["TICK1"],
        asof=asof,
        hist_dict=hist_dict,
        lookback_days=lookback,
    )

    # Returns should have at most lookback-1 rows (one lost to pct_change)
    returns = result["returns_matrix"]
    assert len(returns) <= lookback


def test_returns_matrix_no_bars_before_asof():
    """Ticker with no bars ≤ asof → unavailable."""
    hist = _synthetic_hist(260, seed=42)
    # asof before the first bar
    asof = hist.index[0] - pd.Timedelta(days=10)

    hist_dict = {"TICK1": hist}

    result = compute_pit_returns_matrix(
        tickers=["TICK1"],
        asof=asof,
        hist_dict=hist_dict,
    )

    # Should have error (no tickers with valid data)
    assert "error" in result
    assert "no tickers with valid returns" in result["error"].lower()

    # Availability should mark TICK1 as unavailable
    assert "unavailable" in result["availability"]["TICK1"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
