"""Unit tests: multi-signal entry leverage + risk filters (real default_policy)."""
import os
import sys

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from backtest.policy import default_policy, extract_leverage_flags, choose_entry  # noqa: E402


def _scores(
    overall: float,
    *,
    stack: str = "Mixed",
    golden: bool = False,
    consensus: str = "Neutral",
    var95: float = 15.0,
    regime: str = "Neutral",
    finbert_score: float = 50.0,
    finbert_label: str = "Neutral",
    macd: str = "Neutral",
    adx: float = 15.0,
    plus_di: float = 20.0,
    minus_di: float = 18.0,
):
    return {
        "ticker": "TEST",
        "overall": overall,
        "signals": {
            "multi_h": {"consensus_direction": consensus, "horizons": {"5d": {"direction": consensus}}},
            "mc_risk": {"var_95": var95},
            "regime": {"regime": regime},
            "trend": {"stack": stack, "golden_cross": golden, "death_cross": False},
            "adx": {"adx": adx, "plus_di": plus_di, "minus_di": minus_di},
            "classic": {"macd_cross": macd, "rsi": 55},
            "finbert": {"sentiment_score": finbert_score, "overall_sentiment": finbert_label},
        },
    }


def test_trend_path_allows_long_mid_score():
    """Constructive SMA stack + Medium conv can long without overall>=60."""
    s = _scores(54.0, stack="Bullish", golden=True, consensus="Neutral", macd="Bullish")
    sig = default_policy(s, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    assert sig.action == "long", sig.rationale
    assert "trend" in sig.rationale.lower() or "stack" in sig.rationale.lower()
    assert sig.suggested_risk_pct > 0


def test_high_var_blocks_trend_long():
    s = _scores(55.0, stack="Bullish", golden=True, var95=35.0, regime="Neutral")
    sig = default_policy(s, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    assert sig.action == "flat"
    assert "risk filter" in sig.rationale
    assert "VaR" in sig.rationale


def test_bear_regime_blocks_long():
    s = _scores(62.0, stack="Bullish", consensus="Neutral", regime="Bear", var95=18.0)
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "flat"
    assert "Bear" in sig.rationale or "risk filter" in sig.rationale


def test_bearish_consensus_blocks_soft_long():
    s = _scores(55.0, stack="Bullish", consensus="Bearish", var95=12.0)
    sig = default_policy(s, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    assert sig.action == "flat"


def test_bullish_consensus_path_demoted_by_default():
    """Path C multi-horizon entry is OFF by default (feature audit)."""
    s = _scores(56.0, stack="Mixed", consensus="Bullish", macd="Neutral")
    sig = default_policy(s, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    assert sig.action == "flat", sig.rationale
    assert "multi-horizon" not in sig.rationale.lower()


def test_bullish_consensus_path_opt_in():
    s = _scores(56.0, stack="Mixed", consensus="Bullish", macd="Neutral")
    sig = default_policy(
        s,
        quant_output={"quantitative_conviction": "Medium"},
        current_price=100.0,
        allow_multi_horizon_entry=True,
    )
    assert sig.action == "long", sig.rationale
    assert "multi-horizon" in sig.rationale.lower() or "Bullish" in sig.rationale


def test_finbert_bull_changes_path_vs_neutral():
    neutral = _scores(54.0, stack="Mixed", consensus="Neutral", finbert_score=50.0)
    bull = _scores(54.0, stack="Mixed", consensus="Neutral", finbert_score=65.0, finbert_label="Positive")
    sig_n = default_policy(neutral, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    sig_b = default_policy(bull, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    # Neutral FinBERT stub should not open on path D alone without trend
    assert sig_n.action == "flat" or "FinBERT" not in sig_n.rationale
    assert sig_b.action == "long", sig_b.rationale
    assert "FinBERT" in sig_b.rationale or sig_b.suggested_risk_pct > 0


def test_extract_leverage_flags_news_active():
    s = _scores(50, finbert_score=50.0)
    lev = extract_leverage_flags(s["signals"])
    assert lev["news_active"] is False
    s2 = _scores(50, finbert_score=62.0, finbert_label="Positive")
    lev2 = extract_leverage_flags(s2["signals"])
    assert lev2["news_bull"] is True
    assert lev2["news_active"] is True


def test_choose_entry_pure():
    lev = extract_leverage_flags(_scores(54, stack="Bullish", golden=True)["signals"])
    act, risk, why = choose_entry(54.0, "Medium", lev)
    assert act == "long"
    assert risk > 0


def test_memory_still_blocks_after_leverage():
    s = _scores(55.0, stack="Bullish", golden=True)
    mem = {"block_new_long": True, "flags": ["stop_cooldown(3d left)"], "risk_multiplier": 0.5}
    sig = default_policy(
        s,
        quant_output={"quantitative_conviction": "Medium"},
        current_price=100.0,
        memory=mem,
    )
    assert sig.action == "flat"
    assert "memory block" in sig.rationale


if __name__ == "__main__":
    test_trend_path_allows_long_mid_score()
    test_high_var_blocks_trend_long()
    test_bear_regime_blocks_long()
    test_bearish_consensus_blocks_soft_long()
    test_bullish_consensus_path_demoted_by_default()
    test_bullish_consensus_path_opt_in()
    test_finbert_bull_changes_path_vs_neutral()
    test_extract_leverage_flags_news_active()
    test_choose_entry_pure()
    test_memory_still_blocks_after_leverage()
    print("All policy leverage tests passed.")
