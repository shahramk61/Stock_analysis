"""Correctness tests for the backtest engine / data / policy."""
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from backtest.data import (  # noqa: E402
    _flatten_ohlcv,
    asof_snapshot,
    get_price_series,
    trading_days_in_range,
)
from backtest.policy import default_policy, position_size_shares  # noqa: E402
from backtest.metrics import compute_metrics  # noqa: E402
from backtest.engine import Backtester  # noqa: E402


def _synth_hist(n=300, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=datetime(2025, 6, 30), periods=n)
    rets = rng.normal(0.0004, 0.012, size=n)
    close = 100 * np.cumprod(1 + rets)
    high = close * 1.01
    low = close * 0.99
    open_ = close * (1 + rng.normal(0, 0.001, n))
    vol = rng.integers(1e6, 5e6, n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def test_flatten_multiindex():
    raw = _synth_hist(50)
    # Simulate yf MultiIndex columns
    mi = pd.MultiIndex.from_product([raw.columns, ["AAPL"]])
    multi = raw.copy()
    multi.columns = mi
    flat = _flatten_ohlcv(multi)
    assert list(flat.columns) == ["Open", "High", "Low", "Close", "Volume"]
    s = get_price_series(flat)
    assert isinstance(s, pd.Series)
    assert s.dtype == float or np.issubdtype(s.dtype, np.floating)


def test_asof_no_future():
    hist = _synth_hist(200)
    data = {"ticker": "TEST", "history": hist, "info": {"trailingPE": 999}, "start": "2024-01-01", "end": "2025-06-01"}
    mid = hist.index[100]
    snap = asof_snapshot(data, mid)
    assert snap["history"].index.max() <= pd.Timestamp(mid)
    assert snap["info"] == {}  # no live info leak


def test_position_size_cash_cap():
    # Tight stop would want huge size without cap
    shares = position_size_shares(10_000, 0.01, 100.0, stop_price=99.5, max_notional_pct=0.95)
    assert shares * 100 <= 10_000 * 0.95 + 1e-6
    assert shares > 0


def test_metrics_use_initial_capital():
    eq = pd.DataFrame(
        {"equity": [9_800.0, 10_000.0, 10_200.0]},
        index=pd.bdate_range("2025-01-01", periods=3),
    )
    eq["returns"] = eq["equity"].pct_change().fillna(0)
    m = compute_metrics(eq, [{"pnl": 200}], initial_capital=10_000.0)
    # 10200/10000 - 1 = 2%
    assert abs(m["total_return"] - 2.0) < 1e-6


def test_strict_policy_no_demo_long_at_50():
    scores = {
        "overall": 50.0,
        "signals": {
            "multi_h": {"consensus_direction": "Neutral", "horizons": {}},
            "mc_risk": {"var_95": 15.0},
            "regime": {"regime": "Neutral"},
            "classic": {},
            "adx": {},
            "trend": {},
        },
    }
    sig = default_policy(scores, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    # Strict: need score>=60 for High-only path
    assert sig.action == "flat"


def test_strict_policy_long_when_qualified():
    scores = {
        "overall": 72.0,
        "signals": {
            "multi_h": {"consensus_direction": "Bullish", "horizons": {"5d": {"direction": "Bullish"}}},
            "mc_risk": {"var_95": 12.0},
            "regime": {"regime": "Bull"},
            "classic": {"macd_cross": "Bullish"},
            "adx": {"adx": 30, "plus_di": 25, "minus_di": 10},
            "trend": {"stack": "Bullish"},
        },
    }
    sig = default_policy(scores, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    assert sig.action == "long"
    assert sig.suggested_risk_pct > 0


def test_engine_flat_exits_and_next_open(monkeypatch=None):
    """Minimal integration: inject synthetic data into Backtester."""
    hist = _synth_hist(120, seed=1)
    start = str(hist.index[40].date())
    end = str(hist.index[-1].date())

    bt = Backtester(
        ticker="TEST",
        start=start,
        end=end,
        initial_capital=50_000,
        rebalance_days=5,
        fast_mode=True,
        use_forecasts=False,
    )
    # Inject data (bypass yfinance)
    bt._data = {
        "ticker": "TEST",
        "history": hist,
        "info": {},
        "start": start,
        "end": end,
        "fundamentals_pit": False,
    }

    # Force policy via monkeypatch on calculate_pillars path — simpler: patch default_policy
    import backtest.engine as eng_mod
    actions = ["long", "long", "flat", "flat", "long", "flat"]
    state = {"i": 0}

    def fake_policy(scores, **kwargs):
        from backtest.policy import TradeSignal
        i = state["i"]
        state["i"] += 1
        act = actions[i % len(actions)]
        px = kwargs.get("current_price") or 100.0
        return TradeSignal(
            ticker="TEST",
            asof="n/a",
            action=act,
            conviction="High",
            overall_score=70.0 if act == "long" else 40.0,
            suggested_risk_pct=0.01 if act == "long" else 0.0,
            stop_price=px * 0.9 if act == "long" else None,
            rationale=f"forced {act}",
        )

    # Also stub calculate_pillars import inside loop by patching score module
    import types
    score_mod = types.ModuleType("score")
    score_mod.calculate_pillars = lambda *a, **k: {
        "overall": 70.0,
        "signals": {"atr_vol": {"atr_percent": 2.0}, "mc_risk": {"var_95": 10}},
    }
    sys.modules["score"] = score_mod

    # quant stub
    qa_pkg = types.ModuleType("agents")
    qa_sub = types.ModuleType("agents.quantitative_analyst")
    qa_mod = types.ModuleType("agents.quantitative_analyst.quantitative_analyst")
    qa_mod.create_quantitative_analyst = lambda **k: (lambda state: {"quantitative_conviction": "High"})
    sys.modules["agents"] = qa_pkg
    sys.modules["agents.quantitative_analyst"] = qa_sub
    sys.modules["agents.quantitative_analyst.quantitative_analyst"] = qa_mod

    orig = eng_mod.default_policy
    eng_mod.default_policy = fake_policy
    try:
        result = bt.run()
    finally:
        eng_mod.default_policy = orig

    assert not result.equity_curve.empty
    # Equity curve is daily
    assert len(result.equity_curve) >= 10
    # Metrics vs initial capital
    assert "total_return" in result.metrics
    assert result.metrics.get("initial_capital") == 50_000 or result.metrics.get("final_equity") is not None
    # If we had longs then flat, trades should have exit reasons
    for t in result.trades:
        assert "entry_date" in t
        if "exit_date" in t:
            assert t.get("exit_reason") in ("flat", "stop", "end_of_backtest", "signal")


if __name__ == "__main__":
    test_flatten_multiindex()
    test_asof_no_future()
    test_position_size_cash_cap()
    test_metrics_use_initial_capital()
    test_strict_policy_no_demo_long_at_50()
    test_strict_policy_long_when_qualified()
    test_engine_flat_exits_and_next_open()
    print("All backtest engine tests passed.")
