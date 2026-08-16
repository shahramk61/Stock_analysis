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


def test_book_not_ready_vetoes():
    """book_ready=false → VETO adds (PM state: paper book not ready)."""
    dec = vet_trade(
        action="long",
        ticker="NEW",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book={"AAPL": {"notional": 10_000, "sector": "Technology"}},
        book_ready=False,  # PM state
        proposed_notional=5_000,
    )
    assert dec.outcome == VET_VETO
    assert any("book_ready" in r.detail.lower() for r in dec.reasons)


def test_empty_book_vetoes_add():
    """Empty book → VETO adds (cannot verify concentration)."""
    dec = vet_trade(
        action="long",
        ticker="NEW",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book={},  # empty
        book_ready=True,
        proposed_notional=10_000,
    )
    assert dec.outcome == VET_VETO
    assert any("empty" in r.detail.lower() for r in dec.reasons)


def test_single_name_cap_vetoes():
    """Single name > 10% cap → VETO (Risk-ratified limit)."""
    book = {
        "AAPL": {"notional": 45_000, "sector": "Technology"},
        "MSFT": {"notional": 45_000, "sector": "Technology"},
    }
    sector_tags = {"NEW": "Healthcare"}
    # Total: 90k + 10k = 100k; NEW: 10k/100k = 10% exactly at limit
    # Add 11k to exceed
    dec = vet_trade(
        action="long",
        ticker="NEW",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        book_ready=True,
        sector_tags=sector_tags,
        correlations={},  # provided but empty (no correlations)
        proposed_notional=11_000,  # 11/101 = 10.9% > 10%
    )
    assert dec.outcome == VET_VETO
    assert any("single" in r.detail.lower() for r in dec.reasons)
    assert "0.10" in dec.reasons[0].detail or "10%" in dec.reasons[0].detail


def test_missing_sector_tag_vetoes():
    """Missing sector tag on add → VETO (cannot prove sector cap)."""
    book = {"AAPL": {"notional": 50_000, "sector": "Technology"}}
    sector_tags = {}  # missing NEW
    dec = vet_trade(
        action="long",
        ticker="NEW",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        book_ready=True,
        sector_tags=sector_tags,
        proposed_notional=5_000,
    )
    assert dec.outcome == VET_VETO
    assert any("sector tag" in r.detail.lower() for r in dec.reasons)


def test_sector_cap_vetoes():
    """Sector > 25% cap → VETO (Risk-ratified limit)."""
    book = {
        "AAPL": {"notional": 15_000, "sector": "Technology"},
        "MSFT": {"notional": 10_000, "sector": "Technology"},
        "XYZ": {"notional": 75_000, "sector": "Healthcare"},
    }
    sector_tags = {"GOOGL": "Technology"}
    # Total: 100k + 5k = 105k
    # Tech sector: 15k + 10k + 5k = 30k / 105k = 28.6% > 25%
    dec = vet_trade(
        action="long",
        ticker="GOOGL",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        book_ready=True,
        sector_tags=sector_tags,
        correlations={},
        proposed_notional=5_000,
    )
    assert dec.outcome == VET_VETO
    assert any("sector" in r.category.lower() and "Technology" in r.detail for r in dec.reasons)


def test_missing_correlation_vetoes():
    """Missing PIT correlation → VETO factor cluster check (fail closed)."""
    book = {
        "AAPL": {"notional": 50_000, "sector": "Technology"},
        "XYZ": {"notional": 50_000, "sector": "Healthcare"},
    }
    sector_tags = {"NEW": "Finance"}  # different sector, passes sector cap
    # Total: 100k + 5k = 105k; Finance: 5k / 105k = 4.8% < 25% OK
    # Single-name: 5k / 105k = 4.8% < 10% OK
    # But missing correlation → VETO
    dec = vet_trade(
        action="long",
        ticker="NEW",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        book_ready=True,
        sector_tags=sector_tags,
        correlations=None,  # missing PIT correlation
        proposed_notional=5_000,
    )
    assert dec.outcome == VET_VETO
    assert any("correlation" in r.detail.lower() or "PIT" in r.detail for r in dec.reasons)


def test_factor_cluster_cap_vetoes():
    """Factor cluster > 35% cap → VETO (Risk-ratified limit)."""
    book = {
        "AAPL": {"notional": 20_000, "sector": "Technology"},
        "MSFT": {"notional": 10_000, "sector": "Finance"},
        "JNJ": {"notional": 10_000, "sector": "Healthcare"},
        "XOM": {"notional": 60_000, "sector": "Energy"},
    }
    sector_tags = {"GOOGL": "Technology"}
    # Total: 100k + 10k = 110k
    # Tech sector: 20k + 10k = 30k / 110k = 27.3% < 25% OK (just under)
    # Actually, let me use Healthcare to be safer
    sector_tags = {"GOOGL": "Healthcare"}
    # Healthcare: 10k + 10k = 20k / 110k = 18.2% < 25% OK
    # Single-name: 10k / 110k = 9.1% < 10% OK
    # Factor cluster: if AAPL-GOOGL and MSFT-GOOGL and JNJ-GOOGL all > 0.60
    # Cluster = 20k + 10k + 10k + 10k = 50k / 110k = 45.5% > 35% VETO
    corr = {
        ("AAPL", "GOOGL"): 0.65,
        ("GOOGL", "MSFT"): 0.70,
        ("GOOGL", "JNJ"): 0.62,
    }
    dec = vet_trade(
        action="long",
        ticker="GOOGL",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        book_ready=True,
        sector_tags=sector_tags,
        correlations=corr,
        proposed_notional=10_000,
    )
    assert dec.outcome == VET_VETO
    assert any("factor cluster" in r.detail.lower() or "cluster" in r.category.lower() for r in dec.reasons)


def test_max_names_vetoes():
    """Book has 20 names → VETO adding 21st (Risk-ratified limit)."""
    book = {f"TICK{i}": {"notional": 5_000, "sector": "Technology"} for i in range(20)}
    sector_tags = {"NEW": "Technology"}
    dec = vet_trade(
        action="long",
        ticker="NEW",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        book_ready=True,
        sector_tags=sector_tags,
        correlations={},
        proposed_notional=1_000,
    )
    assert dec.outcome == VET_VETO
    assert any("20" in r.detail and "names" in r.detail.lower() for r in dec.reasons)


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
    book = {"TEST": {"notional": 10_000, "sector": "Technology"}}
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        book=book,
        book_ready=True,
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


def test_hardcoded_cvar_20_fallback_vetoes():
    """CVaR=20.0 (hardcoded fallback) without MC evidence → VETO."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        cvar_95=20.0,  # hardcoded fallback
        require_cvar=True,
        mc_metadata=None,  # no MC evidence
    )
    assert dec.outcome == VET_VETO
    assert "cvar_95" in dec.missing
    assert any("fallback" in r.detail.lower() for r in dec.reasons)


def test_hardcoded_cvar_28_fallback_vetoes():
    """CVaR=28.0 (hardcoded fallback) without MC evidence → VETO."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        cvar_95=28.0,  # hardcoded fallback
        require_cvar=True,
        mc_metadata={},  # empty metadata, no MC evidence
    )
    assert dec.outcome == VET_VETO
    assert "cvar_95" in dec.missing
    assert any("fallback" in r.detail.lower() for r in dec.reasons)


def test_cvar_20_with_mc_evidence_passes():
    """CVaR=20.0 WITH MC evidence (paths > 0) → ALLOW."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        cvar_95=20.0,
        require_cvar=True,
        mc_metadata={"paths": 10000, "simulations": 252},  # MC ran
    )
    assert dec.outcome == VET_ALLOW


def test_cvar_28_with_mc_evidence_passes():
    """CVaR=28.0 WITH MC evidence (simulations > 0) → ALLOW."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        cvar_95=28.0,
        require_cvar=True,
        mc_metadata={"n_simulations": 1000, "n_paths": 5000},
    )
    assert dec.outcome == VET_ALLOW


def test_cvar_fallback_flag_vetoes():
    """CVaR with explicit fallback flag → VETO."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        cvar_95=20.0,
        require_cvar=True,
        mc_metadata={"paths": 10000, "is_fallback": True},  # explicit fallback flag
    )
    assert dec.outcome == VET_VETO
    assert "cvar_95" in dec.missing


def test_cvar_non_fallback_value_passes():
    """CVaR not in {20.0, 28.0} → no fallback check needed."""
    dec = vet_trade(
        action="long",
        ticker="TEST",
        asof="2026-08-01",
        proposed_risk_pct=0.01,
        var_95=15.0,
        regime="Neutral",
        cvar_95=22.5,  # not a fallback value
        require_cvar=True,
        mc_metadata=None,  # no metadata needed for non-fallback values
    )
    assert dec.outcome == VET_ALLOW


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
    test_book_not_ready_vetoes()
    test_empty_book_vetoes_add()
    test_single_name_cap_vetoes()
    test_missing_sector_tag_vetoes()
    test_sector_cap_vetoes()
    test_missing_correlation_vetoes()
    test_factor_cluster_cap_vetoes()
    test_max_names_vetoes()
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
    test_hardcoded_cvar_20_fallback_vetoes()
    test_hardcoded_cvar_28_fallback_vetoes()
    test_cvar_20_with_mc_evidence_passes()
    test_cvar_28_with_mc_evidence_passes()
    test_cvar_fallback_flag_vetoes()
    test_cvar_non_fallback_value_passes()
    print("All risk gate tests passed.")
