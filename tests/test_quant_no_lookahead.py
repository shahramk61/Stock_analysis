"""
Tests for Quant no-lookahead guards and audit.

Proves:
1. Runtime guard fails when live fundamentals are accessed
2. Static audit detects known leaking helpers
3. Guarded execution prevents leaks during replay
"""

import os
import sys
from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from quant.no_lookahead import (
    LookaheadViolation,
    audit_lookahead_risks,
    enable_lookahead_guard,
    disable_lookahead_guard,
    lookahead_guard,
    patch_yfinance_guards,
)


def test_lookahead_guard_context_manager():
    """Lookahead guard should enable and disable correctly."""
    from quant.no_lookahead import _is_guard_enabled

    # Initially disabled
    assert not _is_guard_enabled()

    # Enable via context manager
    with lookahead_guard():
        assert _is_guard_enabled()

    # Disabled after context exit
    assert not _is_guard_enabled()


def test_lookahead_guard_manual_enable_disable():
    """Manual enable/disable should work."""
    from quant.no_lookahead import _is_guard_enabled

    disable_lookahead_guard()
    assert not _is_guard_enabled()

    enable_lookahead_guard()
    assert _is_guard_enabled()

    disable_lookahead_guard()
    assert not _is_guard_enabled()


def test_audit_detects_leaking_helpers():
    """Static audit should detect known leaking helpers in scripts/."""
    # Run audit on the actual codebase
    fundamental_leaks, info_dict_leaks = audit_lookahead_risks()

    # We expect to find leaks in scripts/score.py and scripts/stock_signals.py
    # Check that at least some leaks are detected
    assert len(fundamental_leaks) > 0 or len(info_dict_leaks) > 0, "Audit should detect known leaks in scripts/"

    # Check that known leaking functions are detected
    leaking_funcs = [
        "calculate_altman_beneish",
        "get_earnings_surprise",
        "calculate_piotroski_f_score",
        "get_quality_accruals_gross_profit",
        "get_finbert_sentiment",
    ]

    detected_patterns = [leak["pattern"] for leak in fundamental_leaks]
    detected_funcs = [
        func
        for func in leaking_funcs
        if any(func in pattern for pattern in detected_patterns)
    ]

    # At least some of the known leaking functions should be detected
    assert len(detected_funcs) > 0, f"Audit should detect at least some of {leaking_funcs}"


def test_audit_detects_info_dict_accesses():
    """Static audit should detect info.get() patterns (live fundamentals)."""
    fundamental_leaks, info_dict_leaks = audit_lookahead_risks()

    # scripts/score.py and scripts/dcf.py use info.get() for live fundamentals
    # Check that at least some are detected
    assert len(info_dict_leaks) > 0, "Audit should detect info dict accesses in scripts/"

    # Check that detected leaks reference the right files
    leaked_files = [leak["file"] for leak in info_dict_leaks]
    assert any("score.py" in f for f in leaked_files) or any(
        "dcf.py" in f for f in leaked_files
    ), "Audit should detect info dict leaks in score.py or dcf.py"


def test_pit_score_with_guard_does_not_leak():
    """PIT score under guard should not trigger violations (it doesn't fetch fundamentals)."""
    from quant.pit_score import compute_pit_score

    # Generate synthetic hist
    n = 200
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(end=datetime.today(), periods=n)
    rets = rng.normal(0.0005, 0.015, size=n)
    close = 100 * np.cumprod(1 + rets)
    high = close * (1 + rng.uniform(0, 0.01, size=n))
    low = close * (1 - rng.uniform(0, 0.01, size=n))
    open_ = close * (1 + rng.normal(0, 0.002, size=n))
    vol = rng.integers(1_000_000, 5_000_000, size=n)
    hist = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=dates,
    )

    asof = hist.index[150]
    hist_asof = hist.loc[:asof].copy()

    # Run PIT score with guard enabled
    with lookahead_guard():
        result = compute_pit_score(ticker="TEST", asof=asof, hist=hist_asof)

    # Should succeed without raising LookaheadViolation
    assert "overall_score" in result


def test_guard_fails_on_simulated_fundamental_access():
    """Guard should fail if we simulate a fundamental access."""
    from quant.no_lookahead import _guard_fundamental_access

    # Guard disabled: should not raise
    disable_lookahead_guard()
    _guard_fundamental_access("Ticker.info")  # Should not raise

    # Guard enabled: should raise
    enable_lookahead_guard()
    with pytest.raises(LookaheadViolation, match="LOOKAHEAD VIOLATION"):
        _guard_fundamental_access("Ticker.info")

    disable_lookahead_guard()


def test_yfinance_patch_guards_ticker_info():
    """Patching yfinance should guard Ticker.info access."""
    try:
        import yfinance as yf
    except ImportError:
        pytest.skip("yfinance not installed")

    # Patch yfinance guards
    patch_yfinance_guards()

    # Create a ticker
    ticker = yf.Ticker("AAPL")

    # Access info without guard: should work (or fail due to network, but not LookaheadViolation)
    disable_lookahead_guard()
    try:
        _ = ticker.info  # May fail due to network, that's OK
    except LookaheadViolation:
        pytest.fail("Guard should not be active when disabled")
    except Exception:
        pass  # Network or other error, OK

    # Access info with guard: should raise LookaheadViolation
    enable_lookahead_guard()
    with pytest.raises(LookaheadViolation, match="LOOKAHEAD VIOLATION"):
        _ = ticker.info

    disable_lookahead_guard()


def test_audit_can_scan_custom_paths():
    """Audit should accept custom scan paths."""
    # Create a temporary test file with a leak
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
import yfinance as yf

def leaking_func(ticker):
    stock = yf.Ticker(ticker)
    bs = stock.balance_sheet  # This is a leak
    return bs
"""
        )
        temp_path = f.name

    try:
        # Run audit on the temp file
        fundamental_leaks, _ = audit_lookahead_risks(scan_paths=[temp_path])

        # Should detect the balance_sheet access
        assert len(fundamental_leaks) > 0
        assert any("balance_sheet" in leak["pattern"] for leak in fundamental_leaks)
    finally:
        os.unlink(temp_path)


def test_walkforward_with_guard_enabled():
    """Walk-forward replay with guard should not trigger violations."""
    from quant.walkforward import run_walkforward

    # Generate synthetic hist
    n = 200
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(end=datetime.today(), periods=n)
    rets = rng.normal(0.0005, 0.015, size=n)
    close = 100 * np.cumprod(1 + rets)
    high = close * (1 + rng.uniform(0, 0.01, size=n))
    low = close * (1 - rng.uniform(0, 0.01, size=n))
    open_ = close * (1 + rng.normal(0, 0.002, size=n))
    vol = rng.integers(1_000_000, 5_000_000, size=n)
    hist = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=dates,
    )

    start = hist.index[50]
    end = hist.index[150]

    # Run walk-forward (it uses lookahead_guard internally)
    result = run_walkforward(
        ticker="TEST",
        start=start,
        end=end,
        hist=hist,
        rebalance_days=40,
    )

    # Should succeed without raising LookaheadViolation
    assert "steps" in result
    assert len(result["steps"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
