"""Walk-forward safety and policy effects for DecisionMemory."""
import os
import sys

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from backtest.memory import DecisionMemory, MemoryConfig  # noqa: E402
from backtest.policy import default_policy  # noqa: E402


def _base_scores(overall=65.0):
    return {
        "overall": overall,
        "ticker": "TEST",
        "signals": {
            "multi_h": {"consensus_direction": "Neutral", "horizons": {}},
            "mc_risk": {"var_95": 12.0},
            "regime": {"regime": "Neutral"},
            "classic": {"macd_cross": "Bullish"},
            "adx": {"adx": 20, "plus_di": 22, "minus_di": 15},
            "trend": {"stack": "Bullish"},
        },
    }


def test_no_future_trade_pnl_in_snapshot():
    mem = DecisionMemory(ticker="TEST", config=MemoryConfig(stop_cooldown_days=5))
    mem.record_decision({"date": "2026-07-10", "action": "long", "overall_score": 63})
    mem.record_trade({
        "entry_date": "2026-07-11",
        "exit_date": "2026-07-20",
        "exit_reason": "stop",
        "pnl": -100.0,
        "score": 63,
    })
    # Before exit is known
    snap = mem.snapshot_asof("2026-07-15", position=10, entry_price=100, current_price=98)
    closed = snap["closed_trades"]
    assert closed == [], "must not see PnL before exit_date"
    assert snap["open_position"] is not None
    assert snap["last_stop"] is None

    # On/after exit
    snap2 = mem.snapshot_asof("2026-07-20")
    assert len(snap2["closed_trades"]) == 1
    assert snap2["last_stop"] is not None
    assert snap2["stop_cooldown_active"] is True


def test_stop_cooldown_blocks_policy_long():
    mem = DecisionMemory(ticker="TEST", config=MemoryConfig(stop_cooldown_days=5))
    mem.record_trade({
        "entry_date": "2026-07-10",
        "exit_date": "2026-07-15",
        "exit_reason": "stop",
        "pnl": -50.0,
        "score": 63,
    })
    snap = mem.snapshot_asof("2026-07-17")
    assert snap["stop_cooldown_active"] is True
    pol = mem.apply_to_policy_inputs(snap)
    assert pol["block_new_long"] is True

    sig = default_policy(
        _base_scores(63),
        quant_output={"quantitative_conviction": "High"},
        current_price=100.0,
        memory=pol,
    )
    assert sig.action == "flat"
    assert "memory block" in sig.rationale


def test_loss_streak_cuts_size():
    mem = DecisionMemory(
        ticker="TEST",
        config=MemoryConfig(stop_cooldown_days=0, loss_streak_size_cut=2, loss_streak_risk_mult=0.5),
    )
    mem.record_trade({"entry_date": "2026-07-01", "exit_date": "2026-07-02", "pnl": -10, "exit_reason": "flat"})
    mem.record_trade({"entry_date": "2026-07-03", "exit_date": "2026-07-04", "pnl": -20, "exit_reason": "stop"})
    snap = mem.snapshot_asof("2026-07-05")
    assert snap["loss_streak"] == 2
    assert snap["risk_multiplier"] <= 0.5
    pol = mem.apply_to_policy_inputs(snap)
    sig = default_policy(
        _base_scores(72),
        quant_output={"quantitative_conviction": "High"},
        current_price=100.0,
        memory=pol,
    )
    # May be long but size cut
    if sig.action == "long":
        assert sig.suggested_risk_pct < 0.01 or "memory size cut" in sig.rationale
    # With score 72 + High + Neutral consensus, path is score>=60 High
    # consensus neutral -> long with size cut
    assert "memory" in sig.rationale or sig.suggested_risk_pct <= 0.01


def test_decisions_after_asof_excluded():
    mem = DecisionMemory(ticker="TEST")
    mem.record_decision({"date": "2026-07-10", "action": "flat"})
    mem.record_decision({"date": "2026-07-20", "action": "long"})
    past = mem.decisions_asof("2026-07-15")
    assert len(past) == 1
    assert past[0]["date"] == "2026-07-10"


def test_summary_is_facts_only():
    mem = DecisionMemory(ticker="AAPL")
    mem.record_trade({
        "entry_date": "2026-07-16",
        "exit_date": "2026-07-31",
        "exit_reason": "stop",
        "pnl": -1453.8,
        "score": 63.1,
    })
    snap = mem.snapshot_asof("2026-07-31")
    text = mem.summary_text(snap)
    assert "Decision Memory" in text
    assert "stop" in text.lower() or "1453" in text or "63.1" in text


if __name__ == "__main__":
    test_no_future_trade_pnl_in_snapshot()
    test_stop_cooldown_blocks_policy_long()
    test_loss_streak_cuts_size()
    test_decisions_after_asof_excluded()
    test_summary_is_facts_only()
    print("All decision memory tests passed.")
