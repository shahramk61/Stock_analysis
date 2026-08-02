"""
Durable tests for GME audit findings: multi-horizon Path C vs Low conviction,
high VaR hard block, and forecasts-off empty horizons via real score path.

These drive shipped policy/score code — not hard-coded audit conclusions alone.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from backtest.policy import (  # noqa: E402
    choose_entry,
    default_policy,
    extract_leverage_flags,
)
from score import calculate_pillars  # noqa: E402


def _synth_hist(n: int = 260, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-07-30", periods=n)
    # Mild downtrend with noise
    rets = rng.normal(-0.001, 0.02, size=n)
    close = 25 * np.cumprod(1 + rets)
    high = close * 1.02
    low = close * 0.98
    open_ = np.r_[close[0], close[:-1]]
    vol = rng.integers(1e6, 5e6, n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def test_path_c_blocked_when_conviction_low_even_if_consensus_bullish():
    """GME month finding: multi-h Bullish + Low quant never opens Path C."""
    lev = {
        "consensus": "Bullish",
        "consensus_bull": True,
        "consensus_bear": False,
        "trend_bull": False,
        "trend_bull_strong": False,
        "trend_bear": False,
        "stack": "Mixed",
        "macd_cross": "Bullish",
        "adx": 19.0,
        "news_bull": False,
        "news_bear": False,
        "news_active": False,
        "finbert_score": 50.0,
        "regime": "Neutral",
        "regime_bear": False,
        "var95": 68.0,
        "high_var": True,
        "elevated_var": True,
    }
    # Path C off by default even with Medium + Bullish multi-h
    action_off, risk_off, rat_off = choose_entry(54.8, "Medium", lev)
    assert action_off == "flat", rat_off
    assert "Bullish multi-horizon" not in rat_off
    # Mid score qualifies for Path C when opt-in, but Low conv still blocks
    action, risk, rationale = choose_entry(
        54.8, "Low", lev, allow_multi_horizon_entry=True
    )
    assert action == "flat", rationale
    assert risk == 0.0
    assert "Bullish multi-horizon" not in rationale
    # With Medium conv + opt-in, Path C can propose long before VaR filter
    action_m, risk_m, rat_m = choose_entry(
        54.8, "Medium", lev, allow_multi_horizon_entry=True
    )
    assert action_m == "long", rat_m
    assert "Bullish multi-horizon" in rat_m
    assert risk_m > 0


def test_high_var_hard_block_flats_path_c_long():
    """Even if multi-h path would long, VaR>30 hard-filters to flat (GME-like)."""
    scores = {
        "overall": 57.0,
        "signals": {
            "multi_h": {
                "consensus_direction": "Bullish",
                "horizons": {
                    "5d": {"direction": "Bullish", "model_disagreement": 1.0},
                    "10d": {"direction": "Bullish"},
                    "20d": {"direction": "Neutral"},
                },
            },
            "mc_risk": {"var_95": 67.4, "risk_level": "High"},
            "regime": {"regime": "Neutral"},
            # Neutral tech so Path B (trend) does not fire; Path C (multi-h) does
            "classic": {"macd_cross": "Neutral"},
            "adx": {"adx": 12.0, "plus_di": 15.0, "minus_di": 15.0},
            "trend": {"stack": "Mixed", "death_cross": False, "golden_cross": False},
            "finbert": {"sentiment_score": 50.0, "overall_sentiment": "Neutral"},
        },
    }
    # Medium conv + Path C opt-in → long candidate, then hard VaR filter → flat
    pre = choose_entry(
        57.0,
        "Medium",
        extract_leverage_flags(scores["signals"]),
        allow_multi_horizon_entry=True,
    )
    assert pre[0] == "long" and "Bullish multi-horizon" in pre[2], pre
    sig = default_policy(
        scores,
        quant_output={"quantitative_conviction": "Medium"},
        current_price=21.72,
        atr_pct=2.0,
        allow_multi_horizon_entry=True,
    )
    assert sig.action == "flat", sig.rationale
    assert "VaR" in sig.rationale or "risk filter" in sig.rationale


def test_forecasts_off_empty_multi_horizon_via_score():
    """Shipped score path: use_forecasts=False → empty horizons + Neutral consensus."""
    hist = _synth_hist()
    scores = calculate_pillars(
        {
            "ticker": "GME",
            "info": {},
            "history": hist,
            "current_price": float(hist["Close"].iloc[-1]),
        },
        "Balanced",
        compute_dynamic_weights=False,
        hist=hist,
        asof=str(hist.index[-1].date()),
        use_gpu_signals=False,
        use_forecasts=False,
    )
    multi = (scores.get("signals") or {}).get("multi_h") or {}
    assert multi.get("horizons") == {} or multi.get("horizons") is None or len(multi.get("horizons") or {}) == 0
    assert str(multi.get("consensus_direction", "Neutral")) in ("Neutral", "N/A", "")
    lev = extract_leverage_flags(scores.get("signals") or {})
    assert lev["consensus_bull"] is False


def test_extract_leverage_flags_reads_multi_h_bullish():
    signals = {
        "multi_h": {"consensus_direction": "Bullish", "horizons": {"5d": {"direction": "Bullish"}}},
        "mc_risk": {"var_95": 10},
        "regime": {"regime": "Bull"},
        "trend": {"stack": "Bullish"},
        "classic": {},
        "adx": {},
        "finbert": {"sentiment_score": 50.0, "overall_sentiment": "Neutral"},
    }
    lev = extract_leverage_flags(signals)
    assert lev["consensus_bull"] is True
    assert lev["consensus"] == "Bullish"


if __name__ == "__main__":
    test_path_c_blocked_when_conviction_low_even_if_consensus_bullish()
    test_high_var_hard_block_flats_path_c_long()
    test_forecasts_off_empty_multi_horizon_via_score()
    test_extract_leverage_flags_reads_multi_h_bullish()
    print("All GME forecast/policy audit tests passed.")
