"""
Tests for Quant walk-forward replay.

Proves:
1. Walk-forward asof dates are strictly non-decreasing
2. Score at T is invariant to bars after T
3. Realized returns are attached AFTER asof (not fed back into score)
"""

import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from quant.walkforward import run_walkforward


def _synthetic_hist(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV history."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=datetime.today(), periods=n)
    rets = rng.normal(0.0005, 0.015, size=n)
    close = 100 * np.cumprod(1 + rets)
    high = close * (1 + rng.uniform(0, 0.01, size=n))
    low = close * (1 - rng.uniform(0, 0.01, size=n))
    open_ = close * (1 + rng.normal(0, 0.002, size=n))
    vol = rng.integers(1_000_000, 5_000_000, size=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=dates,
    )


def test_walkforward_asof_dates_strictly_increasing():
    """Walk-forward asof dates must be strictly non-decreasing."""
    hist = _synthetic_hist(260)
    start = hist.index[50]
    end = hist.index[200]

    result = run_walkforward(
        ticker="TEST",
        start=start,
        end=end,
        hist=hist,
        rebalance_days=20,
    )

    steps = result["steps"]
    assert len(steps) > 1

    # Check that asof dates are strictly increasing
    asof_dates = [pd.Timestamp(step["asof"]) for step in steps]
    for i in range(1, len(asof_dates)):
        assert asof_dates[i] > asof_dates[i - 1], f"Asof dates not increasing: {asof_dates[i-1]} >= {asof_dates[i]}"


def test_walkforward_score_invariant_to_future():
    """Score at T in walk-forward must not change if future bars are mutated."""
    hist = _synthetic_hist(260)
    start = hist.index[50]
    end = hist.index[150]

    # Run walk-forward with original hist
    result1 = run_walkforward(
        ticker="TEST",
        start=start,
        end=end,
        hist=hist,
        rebalance_days=40,
        attach_realized_returns=False,
    )

    # Mutate bars after end (should not affect scores)
    hist_mutated = hist.copy()
    hist_mutated.loc[hist_mutated.index[180:], "Close"] *= 1.5

    # Run walk-forward again with mutated hist
    result2 = run_walkforward(
        ticker="TEST",
        start=start,
        end=end,
        hist=hist_mutated,
        rebalance_days=40,
        attach_realized_returns=False,
    )

    # Scores at each step should be identical
    steps1 = result1["steps"]
    steps2 = result2["steps"]

    assert len(steps1) == len(steps2)
    for s1, s2 in zip(steps1, steps2):
        assert s1["asof"] == s2["asof"]
        assert s1["score"] == s2["score"], f"Score changed at {s1['asof']}: {s1['score']} != {s2['score']}"


def test_walkforward_realized_returns_are_forward_looking():
    """Realized returns should be computed from future bars (not used in score)."""
    hist = _synthetic_hist(260)
    start = hist.index[50]
    end = hist.index[150]

    result = run_walkforward(
        ticker="TEST",
        start=start,
        end=end,
        hist=hist,
        rebalance_days=40,
        attach_realized_returns=True,
        realized_horizons=[5, 20],
    )

    steps = result["steps"]
    assert len(steps) > 0

    # Check that realized returns exist and reference future dates
    for step in steps:
        asof = pd.Timestamp(step["asof"])
        realized = step.get("realized_returns")

        if realized:
            for horizon_key, ret_data in realized.items():
                future_date = pd.Timestamp(ret_data["future_date"])
                # Future date must be after asof
                assert future_date > asof, f"Realized return future_date {future_date} not after asof {asof}"

                # Check that return is computed correctly
                asof_close = ret_data["asof_close"]
                future_close = ret_data["future_close"]
                expected_return = (future_close / asof_close - 1) * 100
                actual_return = ret_data["return_pct"]
                assert abs(actual_return - expected_return) < 0.01, "Realized return calculation mismatch"


def test_walkforward_summary_statistics():
    """Walk-forward should produce valid summary statistics."""
    hist = _synthetic_hist(260)
    start = hist.index[50]
    end = hist.index[200]

    result = run_walkforward(
        ticker="TEST",
        start=start,
        end=end,
        hist=hist,
        rebalance_days=20,
    )

    summary = result["summary"]
    assert summary["num_steps"] > 0
    assert summary["num_valid_scores"] > 0
    assert summary["avg_score"] is not None
    assert summary["min_score"] is not None
    assert summary["max_score"] is not None

    # Check that min <= avg <= max
    assert summary["min_score"] <= summary["avg_score"] <= summary["max_score"]


def test_walkforward_no_hist_fails_gracefully():
    """Walk-forward should fail gracefully if no hist is provided."""
    with pytest.raises(ValueError, match="pre-loaded hist"):
        run_walkforward(
            ticker="TEST",
            start="2023-01-01",
            end="2023-12-31",
            hist=None,
        )


def test_walkforward_empty_range():
    """Walk-forward should handle empty date range gracefully."""
    hist = _synthetic_hist(260)
    # Start after end (invalid range)
    start = hist.index[200]
    end = hist.index[50]

    result = run_walkforward(
        ticker="TEST",
        start=start,
        end=end,
        hist=hist,
        rebalance_days=20,
    )

    # Should return error or empty steps
    assert "error" in result or len(result["steps"]) == 0


def test_walkforward_rebalance_frequency():
    """Walk-forward should respect rebalance frequency."""
    hist = _synthetic_hist(260)
    start = hist.index[50]
    end = hist.index[200]

    # Test with different rebalance frequencies
    for rebal_days in [10, 20, 40]:
        result = run_walkforward(
            ticker="TEST",
            start=start,
            end=end,
            hist=hist,
            rebalance_days=rebal_days,
        )

        steps = result["steps"]
        # Check that rebalance frequency is respected (approximately)
        if len(steps) > 1:
            asof_dates = [pd.Timestamp(step["asof"]) for step in steps]
            # Average gap between steps should be close to rebal_days (in trading days)
            # We allow some variance due to weekend/holiday skips
            for i in range(1, len(asof_dates)):
                gap = (asof_dates[i] - asof_dates[i - 1]).days
                # Gap should be roughly rebal_days (allow 50% variance for weekends)
                assert gap >= rebal_days * 0.5, f"Gap {gap} too small for rebal_days={rebal_days}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
