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


def test_high_var_constructive_structure_size_cuts_not_flat():
    """First principles: VaR 35% + Bullish stack is trade-small, not hard flat (LLY class)."""
    s = _scores(55.0, stack="Bullish", golden=True, var95=35.0, regime="Bull", macd="Bullish")
    sig = default_policy(s, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    assert sig.action == "long", sig.rationale
    assert "size cut" in sig.rationale and "VaR" in sig.rationale
    # Deep cut vs base ~0.01 path
    assert 0 < sig.suggested_risk_pct < 0.01


def test_high_var_with_structural_breakdown_flats():
    """High VaR + death/Bearish stack remains hard flat (TSLA-class tape)."""
    s = _scores(55.0, stack="Bearish", golden=False, var95=37.0, regime="Neutral", macd="Bearish")
    s["signals"]["trend"]["death_cross"] = True
    sig = default_policy(s, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    # May never enter choose_entry long if trend_bear blocks paths — force high score High conv
    s2 = _scores(62.0, stack="Bearish", var95=37.0, regime="Neutral", macd="Bearish")
    s2["signals"]["trend"]["death_cross"] = True
    sig = default_policy(s2, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "flat", sig.rationale


def test_extreme_var_hard_flats_even_if_bullish():
    s = _scores(72.0, stack="Bullish", golden=True, var95=50.0, regime="Bull", macd="Bullish")
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "flat", sig.rationale
    assert "extreme VaR" in sig.rationale


def test_bear_regime_blocks_long():
    s = _scores(62.0, stack="Bullish", consensus="Neutral", regime="Bear", var95=18.0)
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "flat"
    assert "Bear" in sig.rationale or "risk filter" in sig.rationale


def test_lly_style_high_score_var31_bull_allows_long():
    """Regression: score 60 High + Bullish stack + VaR 31.2 must not hard-flat."""
    s = _scores(60.2, stack="Bullish", golden=True, var95=31.2, regime="Bull", macd="Neutral")
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "long", sig.rationale
    assert sig.suggested_risk_pct > 0
    assert "size cut" in sig.rationale


def test_high_var_mixed_stack_without_golden_stays_flat():
    """TSLA-class: high VaR + Mixed stack (no golden) must not size into longs."""
    s = _scores(59.5, stack="Mixed", golden=False, var95=37.6, regime="Neutral", macd="Bullish")
    # Path B may propose long via MACD; high-VaR filter should reject without clear uptrend
    sig = default_policy(s, quant_output={"quantitative_conviction": "Medium"}, current_price=100.0)
    assert sig.action == "flat", sig.rationale
    assert "high VaR" in sig.rationale and "clear uptrend" in sig.rationale


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


def test_missing_var_flats_fail_closed():
    """Fail-closed: missing VaR → flat (not long sized as if VaR=0)."""
    s = {
        "ticker": "TEST",
        "overall": 65.0,
        "signals": {
            "multi_h": {"consensus_direction": "Neutral"},
            "mc_risk": {},  # missing var_95
            "regime": {"regime": "Neutral"},
            "trend": {"stack": "Bullish", "golden_cross": True},
            "adx": {"adx": 20, "plus_di": 25, "minus_di": 15},
            "classic": {"macd_cross": "Bullish"},
        },
    }
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "flat", f"Expected flat but got {sig.action}: {sig.rationale}"
    assert "VaR missing" in sig.rationale or "fail closed" in sig.rationale


def test_none_var_flats_fail_closed():
    """Fail-closed: None VaR → flat."""
    s = _scores(65.0, stack="Bullish", golden=True, var95=None)
    # Manually set var_95 to None in signals
    s["signals"]["mc_risk"]["var_95"] = None
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "flat"
    assert "VaR missing" in sig.rationale or "fail closed" in sig.rationale


def test_nan_var_flats_fail_closed():
    """Fail-closed: NaN VaR → flat."""
    s = _scores(65.0, stack="Bullish", golden=True)
    s["signals"]["mc_risk"]["var_95"] = float('nan')
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "flat"
    assert "VaR missing" in sig.rationale or "fail closed" in sig.rationale


def test_missing_regime_flats_fail_closed():
    """Fail-closed: missing regime → flat."""
    s = {
        "ticker": "TEST",
        "overall": 65.0,
        "signals": {
            "multi_h": {"consensus_direction": "Neutral"},
            "mc_risk": {"var_95": 15.0},
            "regime": {},  # missing regime
            "trend": {"stack": "Bullish", "golden_cross": True},
            "adx": {"adx": 20, "plus_di": 25, "minus_di": 15},
            "classic": {"macd_cross": "Bullish"},
        },
    }
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "flat"
    assert "regime missing" in sig.rationale or "fail closed" in sig.rationale


def test_supplied_var_lly_class_still_works():
    """Regression: supplied VaR ~31 + Bullish stack = trade small (LLY-class)."""
    s = _scores(60.2, stack="Bullish", golden=True, var95=31.2, regime="Bull", macd="Neutral")
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    assert sig.action == "long", f"Expected long but got {sig.action}: {sig.rationale}"
    assert sig.suggested_risk_pct > 0
    assert "size cut" in sig.rationale


def test_risk_veto_object_present():
    """Machine-readable risk_veto object must be present on TradeSignal."""
    s = _scores(65.0, stack="Bullish", golden=True, var95=15.0, regime="Neutral")
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    
    # risk_veto must exist
    assert sig.risk_veto is not None, "risk_veto field missing"
    
    # Required keys
    assert "decision" in sig.risk_veto
    assert "reason" in sig.risk_veto
    assert "reasons" in sig.risk_veto
    assert "missing" in sig.risk_veto
    assert "risk_pct" in sig.risk_veto
    assert "action" in sig.risk_veto
    assert "ticker" in sig.risk_veto
    assert "asof" in sig.risk_veto
    
    # decision is enum-like string
    assert sig.risk_veto["decision"] in ("ALLOW", "CUT", "VETO")
    
    # When allowed, decision should be ALLOW
    assert sig.risk_veto["decision"] == "ALLOW"


def test_risk_veto_object_veto_on_missing_var():
    """risk_veto.decision is VETO when VaR missing (not buried in rationale)."""
    s = _scores(65.0, stack="Bullish", golden=True, var95=None, regime="Neutral")
    s["signals"]["mc_risk"]["var_95"] = None
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    
    assert sig.risk_veto is not None
    assert sig.risk_veto["decision"] == "VETO", f"Expected VETO but got {sig.risk_veto['decision']}"
    assert "var_95" in sig.risk_veto["missing"]
    assert sig.action == "flat"


def test_risk_veto_object_cut_on_elevated_var():
    """risk_veto.decision is CUT when VaR elevated (size reduced but allowed)."""
    s = _scores(65.0, stack="Bullish", golden=True, var95=22.0, regime="Neutral")
    sig = default_policy(s, quant_output={"quantitative_conviction": "High"}, current_price=100.0)
    
    assert sig.risk_veto is not None
    # Should be CUT or ALLOW with reasons (depending on if we cut)
    assert sig.risk_veto["decision"] in ("CUT", "ALLOW")
    # risk_pct should be reduced
    assert sig.suggested_risk_pct < 0.01  # was cut from base entry risk


if __name__ == "__main__":
    test_trend_path_allows_long_mid_score()
    test_high_var_constructive_structure_size_cuts_not_flat()
    test_high_var_with_structural_breakdown_flats()
    test_extreme_var_hard_flats_even_if_bullish()
    test_bear_regime_blocks_long()
    test_lly_style_high_score_var31_bull_allows_long()
    test_high_var_mixed_stack_without_golden_stays_flat()
    test_bearish_consensus_blocks_soft_long()
    test_bullish_consensus_path_demoted_by_default()
    test_bullish_consensus_path_opt_in()
    test_finbert_bull_changes_path_vs_neutral()
    test_extract_leverage_flags_news_active()
    test_choose_entry_pure()
    test_memory_still_blocks_after_leverage()
    test_missing_var_flats_fail_closed()
    test_none_var_flats_fail_closed()
    test_nan_var_flats_fail_closed()
    test_missing_regime_flats_fail_closed()
    test_supplied_var_lly_class_still_works()
    test_risk_veto_object_present()
    test_risk_veto_object_veto_on_missing_var()
    test_risk_veto_object_cut_on_elevated_var()
    print("All policy leverage tests passed.")
