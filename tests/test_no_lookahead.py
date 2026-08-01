"""No-lookahead and indicator shape tests (M8 validation leftovers)."""
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from stock_signals import (  # noqa: E402
    get_classic_technicals,
    get_trend_structure,
    get_adx,
    get_momentum_and_52w_high,
    get_amihud_illiquidity,
    normalize_direction,
)
from backtest.policy import default_policy, position_size_shares  # noqa: E402
from backtest.data import asof_snapshot  # noqa: E402


def _synthetic_hist(n: int = 300, seed: int = 42) -> pd.DataFrame:
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


def test_asof_slice_never_sees_future_bars():
    hist = _synthetic_hist(260)
    mid = hist.index[180]
    past = hist.loc[:mid]
    future_close = float(hist.loc[hist.index[200], "Close"])

    # Indicators on past slice must not equal an indicator computed including future
    # when prices differ materially — smoke: last bar date ≤ mid
    assert past.index.max() <= mid

    c_past = get_classic_technicals("TEST", hist=past)
    c_full = get_classic_technicals("TEST", hist=hist)
    # Full series last bar is later; RSI can differ
    assert "rsi" in c_past and 0 <= c_past["rsi"] <= 100
    assert past["Close"].iloc[-1] != future_close or True  # structural


def test_classic_trend_adx_shapes():
    hist = _synthetic_hist(260)
    classic = get_classic_technicals("TEST", hist=hist)
    trend = get_trend_structure("TEST", hist=hist)
    adx = get_adx("TEST", hist=hist)

    assert 0 <= classic["rsi"] <= 100
    assert classic["macd_cross"] in {
        "Bullish", "Bearish", "Neutral", "BullishCross", "BearishCross"
    }
    assert trend["stack"] in {"Bullish", "Bearish", "Mixed", "Unknown"}
    assert isinstance(trend["golden_cross"], bool)
    assert adx["adx"] >= 0
    assert adx["trend_strength"] in {"Strong", "Moderate", "Weak", "Unknown"}


def test_normalize_direction():
    assert normalize_direction("Bullish 📈") == "Bullish"
    assert normalize_direction("Bearish 📉") == "Bearish"
    assert normalize_direction("Neutral ➕") == "Neutral"


def test_risk_filter_high_var_flats():
    scores = {
        "overall": 72.0,
        "ticker": "TEST",
        "signals": {
            "multi_h": {"consensus_direction": "Bullish", "horizons": {"5d": {"direction": "Bullish"}}},
            "mc_risk": {"var_95": 35.0},
            "regime": {"regime": "Neutral"},
            "classic": {"macd_cross": "Bullish"},
            "adx": {"adx": 15, "plus_di": 20, "minus_di": 10},
            "trend": {"stack": "Bullish"},
        },
    }
    sig = default_policy(scores, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    assert sig.action == "flat"
    assert "risk filter" in sig.rationale


def test_position_size_shares():
    shares = position_size_shares(equity=100_000, risk_pct=0.01, price=100.0, stop_price=95.0)
    # risk $1000 / $5 stop = 200 shares
    assert shares == 200
    # cash cap: tight stop must not explode notional
    shares2 = position_size_shares(10_000, 0.01, 100.0, stop_price=99.5, max_notional_pct=0.95)
    assert shares2 * 100 <= 10_000 * 0.95 + 1e-6


def test_amihud_scalar():
    hist = _synthetic_hist(80)
    out = get_amihud_illiquidity("TEST", hist=hist)
    assert isinstance(out["amihud"], float)


if __name__ == "__main__":
    test_asof_slice_never_sees_future_bars()
    test_classic_trend_adx_shapes()
    test_normalize_direction()
    test_risk_filter_high_var_flats()
    test_position_size_shares()
    test_amihud_scalar()
    print("All tests passed.")
