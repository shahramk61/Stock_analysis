"""Unit tests for Risk veto gate: fail-closed discipline."""
import os
import sys

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from risk import (  # noqa: E402
    vet_trade,
    size_position,
    VET_ALLOW,
    VET_CUT,
    VET_VETO,
)


def test_missing_var_vetoes():
    """Missing VaR → VETO (fail closed)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=None,  # missing
        regime="Neutral",
    )
    assert dec.outcome == VET_VETO
    assert "var_95" in dec.missing
    assert any("var_95" in r.detail for r in dec.reasons)


def test_missing_regime_vetoes():
    """Missing regime → VETO (fail closed)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime=None,  # missing
    )
    assert dec.outcome == VET_VETO
    assert "regime" in dec.missing


def test_missing_asof_vetoes():
    """Missing asof → VETO (fail closed)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof=None,  # missing
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
    )
    assert dec.outcome == VET_VETO
    assert "asof" in dec.missing


def test_live_leak_vetoes():
    """live_leak=True → VETO (lookahead contamination)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        live_leak=True,  # lookahead
    )
    assert dec.outcome == VET_VETO
    assert any("live_leak" in r.detail for r in dec.reasons)


def test_non_pit_fundamentals_vetoes():
    """fundamentals_pit=False → VETO (lookahead contamination)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        fundamentals_pit=False,  # non-PIT
    )
    assert dec.outcome == VET_VETO
    assert any("fundamentals_pit" in r.detail or "non-PIT" in r.detail for r in dec.reasons)


def test_bear_regime_vetoes():
    """Bear regime → VETO new longs (capital protection)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Bear",  # Bear
    )
    assert dec.outcome == VET_VETO
    assert any("Bear" in r.detail for r in dec.reasons)


def test_extreme_var_vetoes():
    """VaR > 45% → VETO regardless of structure."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=50.0,  # extreme
        regime="Bull",
        clear_uptrend=True,
    )
    assert dec.outcome == VET_VETO
    assert any("extreme" in r.detail.lower() for r in dec.reasons)


def test_high_var_with_breakdown_vetoes():
    """VaR > 30% + structural breakdown → VETO."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=35.0,
        regime="Neutral",
        structural_breakdown=True,  # death cross / Bearish stack
    )
    assert dec.outcome == VET_VETO
    assert any("breakdown" in r.detail.lower() for r in dec.reasons)


def test_high_var_without_uptrend_vetoes():
    """VaR > 30% without clear uptrend → VETO (TSLA-class)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=37.0,
        regime="Neutral",
        clear_uptrend=False,  # Mixed stack
    )
    assert dec.outcome == VET_VETO
    assert any("uptrend" in r.detail.lower() for r in dec.reasons)


def test_high_var_with_uptrend_cuts_not_vetoes():
    """VaR > 30% with clear uptrend → CUT (×0.30), not VETO (LLY-class)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=31.0,
        regime="Bull",
        clear_uptrend=True,  # Bullish stack / golden
    )
    assert dec.outcome == VET_CUT
    assert dec.risk_pct < 0.01
    assert dec.risk_pct > 0
    # Deep cut: ~0.01 * 0.30 = 0.003
    assert 0.002 <= dec.risk_pct <= 0.004


def test_elevated_var_cuts():
    """VaR > 20% → moderate CUT (×0.50)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=22.0,
        regime="Neutral",
    )
    assert dec.outcome == VET_CUT
    assert dec.risk_pct == 0.01 * 0.5


def test_stop_cooldown_vetoes():
    """Stop cooldown active → VETO new longs."""
    mem = {
        "block_new_long": True,
        "flags": ["stop_cooldown(3d left)"],
        "risk_multiplier": 0.5,
    }
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        memory_snapshot=mem,
    )
    assert dec.outcome == VET_VETO
    assert any("cooldown" in r.detail.lower() for r in dec.reasons)


def test_loss_streak_cuts():
    """Loss streak ≥2 → CUT (×0.5), not VETO."""
    mem = {
        "block_new_long": False,
        "flags": ["loss_streak=2"],
        "risk_multiplier": 0.5,
    }
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        memory_snapshot=mem,
    )
    assert dec.outcome == VET_CUT
    assert dec.risk_pct == 0.01 * 0.5
    assert any("memory" in r.category.lower() for r in dec.reasons)


def test_missing_book_when_adding_vetoes():
    """Adding a new name without book snapshot → VETO (cannot prove concentration OK)."""
    dec = vet_trade(
        action="long",
        ticker="NEW",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=None,  # missing
        proposed_notional=10_000,
    )
    assert dec.outcome == VET_VETO
    assert any("book" in r.detail.lower() for r in dec.reasons)


def test_single_name_cap_vetoes():
    """Single name > 25% cap → VETO."""
    book = {"EXISTING": 30_000}
    dec = vet_trade(
        action="long",
        ticker="NEW",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        proposed_notional=20_000,  # would be 20/50 = 40% > 25% cap
    )
    assert dec.outcome == VET_VETO
    assert any("single" in r.detail.lower() or "concentration" in r.category.lower() for r in dec.reasons)


def test_cluster_cap_vetoes():
    """Correlated cluster > 40% cap → VETO."""
    book = {"AAPL": 20_000, "MSFT": 20_000, "XYZ": 10_000}  # 50k total
    corr = {
        ("AAPL", "GOOGL"): 0.85,  # high correlation
        ("GOOGL", "MSFT"): 0.60,
    }
    # Add 10k GOOGL: single-name 10/60 = 16.7% < 25% (OK)
    # But cluster AAPL + GOOGL = 30k / 60k = 50% > 40% (VETO)
    dec = vet_trade(
        action="long",
        ticker="GOOGL",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        correlations=corr,
        proposed_notional=10_000,
    )
    assert dec.outcome == VET_VETO
    assert any("cluster" in r.detail.lower() for r in dec.reasons)


def test_research_buy_with_execute_flat_stays_flat():
    """Research BUY (score 65) + Execute VETO (Bear) → stays FLAT (no override)."""
    # Simulates: score 65 → research BUY, but Risk vetoes due to Bear
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Bear",
    )
    assert dec.outcome == VET_VETO
    # Research label cannot override Risk veto


def test_position_size_zero_on_veto():
    """size_position returns 0 shares when vetoed."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=None,  # missing → VETO
        regime="Neutral",
    )
    shares = size_position(dec, equity=100_000, price=100.0, stop_price=95.0)
    assert shares == 0


def test_position_size_nonzero_on_allow():
    """size_position returns shares when allowed."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
    )
    assert dec.outcome == VET_ALLOW
    shares = size_position(dec, equity=100_000, price=100.0, stop_price=95.0)
    # risk $1000 / $5 stop = 200 shares
    assert shares == 200


def test_position_size_cut_uses_reduced_risk():
    """size_position uses reduced risk_pct after CUT."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=22.0,  # elevated → ×0.5
        regime="Neutral",
    )
    assert dec.outcome == VET_CUT
    assert dec.risk_pct == 0.005
    shares = size_position(dec, equity=100_000, price=100.0, stop_price=95.0)
    # risk $500 / $5 = 100 shares
    assert shares == 100


def test_flat_action_allows():
    """Flat action → no veto checks."""
    dec = vet_trade(
        action="flat",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.0,
        var_95=None,  # missing but flat is OK
        regime=None,
    )
    assert dec.outcome == VET_ALLOW
    assert dec.risk_pct == 0.0


def test_cvar_missing_vetoes_when_required():
    """Missing CVaR with require_cvar=True → VETO (opt-in fail closed)."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        cvar_95=None,  # missing
        require_cvar=True,
    )
    assert dec.outcome == VET_VETO
    assert "cvar_95" in dec.missing


def test_cvar_present_passes():
    """CVaR present and finite → pass."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        cvar_95=22.0,  # present
        require_cvar=True,
    )
    assert dec.outcome == VET_ALLOW


def test_combined_cuts_multiply():
    """VaR cut (×0.5) + memory cut (×0.5) → ×0.25 total."""
    mem = {
        "block_new_long": False,
        "risk_multiplier": 0.5,
        "flags": ["loss_streak=2"],
    }
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=22.0,  # elevated → ×0.5
        regime="Neutral",
        memory_snapshot=mem,  # ×0.5
    )
    assert dec.outcome == VET_CUT
    # 0.01 * 0.5 (VaR) * 0.5 (memory) = 0.0025
    assert dec.risk_pct == 0.0025


def test_existing_position_no_concentration_veto():
    """Already have position → no concentration veto when sizing up."""
    book = {"TEST": 10_000}  # already have TEST
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        proposed_notional=50_000,  # would exceed cap if new, but it's existing
    )
    # No concentration veto for existing position
    assert dec.outcome == VET_ALLOW


def test_veto_object_schema():
    """Risk gate exports machine-readable veto object with stable schema."""
    dec = vet_trade(
        action="long",
        ticker="AAPL",
        asof="2026-08-15",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
    )
    
    veto_obj = dec.to_veto_object(action="long", ticker="AAPL", asof="2026-08-15")
    
    # Required keys
    assert "decision" in veto_obj
    assert "reason" in veto_obj
    assert "reasons" in veto_obj
    assert "missing" in veto_obj
    assert "risk_pct" in veto_obj
    assert "action" in veto_obj
    assert "ticker" in veto_obj
    assert "asof" in veto_obj
    
    # decision is enum-like string
    assert veto_obj["decision"] in ("ALLOW", "CUT", "VETO")
    
    # When allowed, decision is ALLOW
    assert veto_obj["decision"] == VET_ALLOW
    assert veto_obj["ticker"] == "AAPL"
    assert veto_obj["asof"] == "2026-08-15"


def test_veto_object_decision_is_veto_not_rationale():
    """VETO is in decision field, not buried in rationale text."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=None,  # missing
        regime="Neutral",
    )
    
    veto_obj = dec.to_veto_object(action="long", ticker="TEST", asof="2026-08-01")
    
    # Trader branches on decision field
    assert veto_obj["decision"] == VET_VETO
    assert veto_obj["action"] == "flat"  # forced flat
    assert veto_obj["risk_pct"] == 0.0
    assert "var_95" in veto_obj["missing"]


if __name__ == "__main__":
    test_missing_var_vetoes()
    test_missing_regime_vetoes()
    test_missing_asof_vetoes()
    test_live_leak_vetoes()
    test_non_pit_fundamentals_vetoes()
    test_bear_regime_vetoes()
    test_extreme_var_vetoes()
    test_high_var_with_breakdown_vetoes()
    test_high_var_without_uptrend_vetoes()
    test_high_var_with_uptrend_cuts_not_vetoes()
    test_elevated_var_cuts()
    test_stop_cooldown_vetoes()
    test_loss_streak_cuts()
    test_missing_book_when_adding_vetoes()
    test_single_name_cap_vetoes()
    test_cluster_cap_vetoes()
    test_research_buy_with_execute_flat_stays_flat()
    test_position_size_zero_on_veto()
    test_position_size_nonzero_on_allow()
    test_position_size_cut_uses_reduced_risk()
    test_flat_action_allows()
    test_cvar_missing_vetoes_when_required()
    test_cvar_present_passes()
    test_combined_cuts_multiply()
    test_existing_position_no_concentration_veto()
    test_veto_object_schema()
    test_veto_object_decision_is_veto_not_rationale()
    print("All risk gate tests passed.")
