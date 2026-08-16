"""Unit tests for trader timing tools."""
import os
import sys
from datetime import datetime, time, date

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from trader.session_clock import (  # noqa: E402
    get_session_state,
    is_market_open,
    should_allow_new_trades,
    SessionState,
    US_EASTERN,
)
from trader.horizon import choose_horizon, Horizon  # noqa: E402
from trader.levels import compute_levels, validate_tape_quality  # noqa: E402
from trader.gate import gate_execution, normalize_action  # noqa: E402
from trader.timing import build_timing_card  # noqa: E402


# Valid book for testing (PM trader_snapshot ready)
_VALID_BOOK = {
    "schema_version": "0.1.0",
    "asof": "2026-08-16T10:00:00Z",
    "book_ready": True,
    "nav_known": True,
    "nav_usd": 100000.0,
    "nav_source": "simulated",
    "open_risk": {
        "names": [],
        "name_count": 0,
        "weights": None
    },
    "capacity": {
        "new_risk": "ALLOW",
        "reason": "NAV seeded, room for new positions"
    },
    "live_broker": False,
    "notes": "Test fixture with NAV ready"
}

def test_weekend_closed():
    """Weekend (Saturday/Sunday) → closed, no new trades."""
    # Saturday Aug 16, 2026
    sat = datetime(2026, 8, 16, 14, 0, tzinfo=US_EASTERN)
    session = get_session_state(sat)
    assert session.state == SessionState.CLOSED_WEEKEND
    assert not session.is_open
    assert not session.allows_new_trades
    # Reason should mention day or closed
    assert len(session.reason) > 0


def test_regular_hours_open():
    """Weekday during regular hours → open, allows trades."""
    # Monday Aug 17, 2026, 10:30 AM ET (market open)
    mon = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon)
    assert session.state == SessionState.REGULAR_HOURS
    assert session.is_open
    assert session.allows_new_trades


def test_premarket_no_new_trades():
    """Pre-market hours → not open, no new trades."""
    # Monday Aug 17, 2026, 8:00 AM ET
    mon = datetime(2026, 8, 17, 8, 0, tzinfo=US_EASTERN)
    session = get_session_state(mon)
    assert session.state == SessionState.PRE_MARKET
    assert not session.is_open
    assert not session.allows_new_trades


def test_after_hours_no_new_trades():
    """After-hours → not open, no new trades."""
    # Monday Aug 17, 2026, 5:00 PM ET
    mon = datetime(2026, 8, 17, 17, 0, tzinfo=US_EASTERN)
    session = get_session_state(mon)
    assert session.state == SessionState.AFTER_HOURS
    assert not session.is_open
    assert not session.allows_new_trades


def test_holiday_closed():
    """Holiday (Christmas) → closed, no new trades."""
    # Dec 25, 2026 (Christmas)
    xmas = datetime(2026, 12, 25, 14, 0, tzinfo=US_EASTERN)
    session = get_session_state(xmas)
    assert session.state == SessionState.CLOSED_HOLIDAY
    assert not session.is_open
    assert not session.allows_new_trades


def test_is_market_open_helpers():
    """Quick helpers work correctly."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    sat_closed = datetime(2026, 8, 16, 14, 0, tzinfo=US_EASTERN)
    
    assert is_market_open(mon_open) is True
    assert is_market_open(sat_closed) is False
    
    assert should_allow_new_trades(mon_open) is True
    assert should_allow_new_trades(sat_closed) is False


# ============================================================================
# Horizon tests
# ============================================================================

def test_explicit_session_mode():
    """Explicit session mode → session horizon."""
    hc = choose_horizon(execution_mode="session", overall_score=55.0)
    assert hc.horizon == Horizon.SESSION
    assert hc.tighter_stop is True
    assert hc.days == 1


def test_explicit_swing_mode():
    """Explicit swing mode → swing horizon."""
    hc = choose_horizon(execution_mode="swing", overall_score=65.0)
    assert hc.horizon == Horizon.SWING
    assert hc.tighter_stop is False


def test_high_volatility_weak_trend_session():
    """High ATR + weak ADX + mid score → session."""
    hc = choose_horizon(
        overall_score=52.0,
        atr_pct=5.0,  # High vol
        adx=18.0,     # Weak trend
    )
    assert hc.horizon == Horizon.SESSION
    assert hc.tighter_stop is True


def test_strong_trend_swing():
    """Strong trend (ADX >= 25) → swing."""
    hc = choose_horizon(
        overall_score=58.0,
        atr_pct=2.5,
        adx=28.0,  # Strong trend
    )
    assert hc.horizon == Horizon.SWING
    assert hc.tighter_stop is False


def test_high_score_swing():
    """High score (>=60) → swing."""
    hc = choose_horizon(
        overall_score=65.0,
        atr_pct=2.0,
        adx=18.0,
    )
    assert hc.horizon == Horizon.SWING


# ============================================================================
# Levels tests
# ============================================================================

def test_missing_price_tape_invalid():
    """Missing current_price → tape_invalid, all levels None."""
    levels = compute_levels(current_price=None)
    assert levels.tape_valid is False
    assert levels.entry_price is None
    assert levels.stop_price is None
    assert "no tape" in levels.reason.lower()


def test_levels_from_policy_stop():
    """Valid price + policy stop → uses policy stop."""
    levels = compute_levels(
        current_price=100.0,
        policy_stop=92.0,
        atr_pct=3.0,
    )
    assert levels.tape_valid is True
    assert levels.entry_price == 100.0
    assert levels.stop_price == 92.0
    assert "policy" in levels.reason.lower()


def test_session_tighter_stop():
    """Session mode → tighter stop."""
    levels = compute_levels(
        current_price=100.0,
        atr_pct=2.0,
        horizon_tighter_stop=True,
    )
    assert levels.tape_valid is True
    assert levels.stop_price is not None
    assert levels.stop_price < 100.0  # Stop below entry
    assert "session" in levels.reason.lower()


def test_atr_fallback_stop():
    """No policy stop, use ATR fallback."""
    levels = compute_levels(
        current_price=100.0,
        atr_pct=4.0,
    )
    assert levels.tape_valid is True
    assert levels.stop_price is not None
    assert levels.stop_price < 100.0
    assert "atr" in levels.reason.lower()


def test_validate_tape_quality():
    """Tape quality validation."""
    valid, reason = validate_tape_quality(current_price=100.0)
    assert valid is True
    
    invalid, reason = validate_tape_quality(current_price=None)
    assert invalid is False
    assert "missing" in reason.lower() or "invalid" in reason.lower()
    
    stale, reason = validate_tape_quality(
        current_price=100.0,
        last_update_age_minutes=120,
        max_stale_minutes=60,
    )
    assert stale is False
    assert "stale" in reason.lower()


# ============================================================================
# Gate tests
# ============================================================================

def test_policy_hint_flat_stays_flat():
    """Policy_hint flat → execute stays flat."""
    gate = gate_execution(
        policy_hint={"action": "flat", "conviction": "Medium"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=_VALID_BOOK
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    # May have risk_veto reason first, policy flat reason after
    assert any("flat" in r.lower() for r in gate.reasons)


def test_research_buy_policy_flat_conflict():
    """Research BUY + policy FLAT → still flat, policy_conflict."""
    gate = gate_execution(
        policy_hint={"action": "flat"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        dual_recommendation={
            "research_recommendation": "BUY",
            "execution_label": "FLAT",
        },
        book=_VALID_BOOK
    )
    assert gate.execute_action == "flat"
    assert gate.policy_conflict is True


def test_memory_block_new_long():
    """Memory block_new_long → flat."""
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=_VALID_BOOK,
        decision_memory={"block_new_long": True, "flags": ["stop_cooldown(3d left)"]},
        session=None,  # Will check now
        levels=compute_levels(current_price=100.0),
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.memory_blocks is True
    assert any("memory block" in r.lower() for r in gate.reasons)


def test_session_closed_blocks():
    """Session closed (weekend) → flat."""
    sat = datetime(2026, 8, 16, 14, 0, tzinfo=US_EASTERN)
    session = get_session_state(sat)
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=_VALID_BOOK,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.session_blocks is True


def test_missing_tape_blocks():
    """Missing tape → flat."""
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=_VALID_BOOK,
        levels=compute_levels(current_price=None),  # No price
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.tape_blocks is True


def test_all_gates_pass_allows_long():
    """All gates pass → execute long."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=_VALID_BOOK,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    assert gate.execute_action == "long"
    assert gate.would_be_flat is False
    assert not gate.risk_veto_blocks
    assert not gate.book_blocks
    assert not gate.memory_blocks
    assert not gate.session_blocks
    assert not gate.tape_blocks


def test_normalize_action():
    """Action normalization."""
    assert normalize_action("buy") == "long"
    assert normalize_action("long") == "long"
    assert normalize_action("LONG") == "long"
    assert normalize_action("hold") == "flat"
    assert normalize_action("sell") == "flat"
    assert normalize_action("flat") == "flat"
    assert normalize_action("short") == "short"
    assert normalize_action(None) == "flat"


# ============================================================================
# Timing card integration tests
# ============================================================================

def test_timing_card_weekend_not_a_trade():
    """Weekend → not a trade."""
    sat = datetime(2026, 8, 16, 14, 0, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        current_price=150.0,
        timestamp=sat,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is False
    assert card.session_blocks is True
    assert card.execute_action == "flat"
    assert card.would_be_flat is True


def test_timing_card_open_market_with_tape():
    """Open market + valid tape + policy long → now a trade."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "long", "stop_price": 145.0},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        current_price=150.0,
        overall_score=62.0,
        atr_pct=2.5,
        adx=22.0,
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is True
    assert card.session_open is True
    assert card.tape_valid is True
    assert card.execute_action == "long"
    assert card.would_be_flat is False
    assert card.entry_price == 150.0
    assert card.stop_price is not None


def test_timing_card_policy_flat_not_a_trade():
    """Open market but policy flat → not a trade."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "flat"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        current_price=150.0,
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is False
    assert card.execute_action == "flat"
    assert card.would_be_flat is True


def test_timing_card_missing_price_not_a_trade():
    """Open market but missing price → not a trade."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        current_price=None,  # Missing!
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is False
    assert not card.tape_valid
    assert card.tape_blocks is True
    assert card.execute_action == "flat"


def test_timing_card_memory_block_not_a_trade():
    """Open market but memory blocks → not a trade."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        decision_memory={
            "block_new_long": True,
            "flags": ["stop_cooldown(2d left)"],
        },
        current_price=150.0,
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is False
    assert card.memory_blocks is True
    assert card.execute_action == "flat"


def test_timing_card_session_vs_swing():
    """Horizon affects stop tightness."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    # Session mode
    card_session = build_timing_card(
        "AAPL",
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        current_price=100.0,
        atr_pct=2.0,
        execution_mode="session",
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    # Swing mode
    card_swing = build_timing_card(
        "AAPL",
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        current_price=100.0,
        atr_pct=2.0,
        execution_mode="swing",
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card_session.horizon == "session"
    assert card_swing.horizon == "swing"
    
    # Session should have tighter stop
    if card_session.stop_price and card_swing.stop_price:
        # Session stop should be closer to entry (tighter)
        session_distance = 100.0 - card_session.stop_price
        swing_distance = 100.0 - card_swing.stop_price
        assert session_distance < swing_distance


# ============================================================================
# PM book tests
# ============================================================================

def test_book_ready_false_blocks():
    """book_ready=false → flat on NEW risk."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    book = {
        "schema_version": "0.1.0",
        "book_ready": False,
        "nav_known": False,
        "nav_usd": None,
        "capacity": {
            "new_risk": "FLAT",
            "reason": "no book → stay flat on new risk"
        },
    }
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=book,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.book_blocks is True
    assert any("book_ready" in r.lower() for r in gate.reasons)


def test_book_missing_blocks():
    """Missing book object → fail closed (flat)."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=None,  # Missing book
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.book_blocks is True
    assert any("snapshot missing" in r.lower() for r in gate.reasons)


def test_book_nav_unknown_blocks():
    """nav_known=false → flat on NEW risk."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    book = {
        "schema_version": "0.1.0",
        "book_ready": True,
        "nav_known": False,  # NAV unknown
        "nav_usd": None,
        "capacity": {
            "new_risk": "ALLOW",
            "reason": "Would allow if NAV was known"
        },
    }
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=book,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.book_blocks is True
    assert any("nav_known" in r.lower() for r in gate.reasons)


def test_book_nav_null_blocks():
    """nav_usd=null → flat on NEW risk."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    book = {
        "schema_version": "0.1.0",
        "book_ready": True,
        "nav_known": True,
        "nav_usd": None,  # NAV null
        "capacity": {
            "new_risk": "ALLOW",
            "reason": "Would allow if NAV was set"
        },
    }
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=book,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.book_blocks is True
    assert any("nav_usd" in r.lower() for r in gate.reasons)


def test_book_capacity_flat_blocks():
    """capacity.new_risk=FLAT → flat."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    book = {
        "schema_version": "0.1.0",
        "book_ready": True,
        "nav_known": True,
        "nav_usd": 100000.0,
        "capacity": {
            "new_risk": "FLAT",  # Capacity says FLAT
            "reason": "Max positions reached"
        },
    }
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=book,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.book_blocks is True
    assert any("capacity.new_risk=flat" in r.lower() for r in gate.reasons)


def test_book_ready_with_cash_passes():
    """book_ready=True, nav_known=True, nav_usd set, capacity ALLOW → book gate passes."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    # Use _VALID_BOOK (already matches trader_snapshot schema)
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=_VALID_BOOK,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    
    # Should pass book gate (other gates may still apply)
    assert gate.book_blocks is False
    assert gate.execute_action == "long"  # All gates pass
    assert gate.would_be_flat is False


def test_book_ready_with_positions_passes():
    """book_ready=True with NAV even with positions → book gate passes."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    book = {
        "schema_version": "0.1.0",
        "book_ready": True,
        "nav_known": True,
        "nav_usd": 100000.0,
        "nav_source": "simulated",
        "open_risk": {
            "names": ["SPY"],
            "name_count": 1,
            "weights": [0.02]
        },
        "capacity": {
            "new_risk": "ALLOW",
            "reason": "Room for more positions"
        },
    }
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=book,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    
    # Should pass book gate
    assert gate.book_blocks is False
    assert gate.execute_action == "long"
    assert gate.would_be_flat is False


def test_book_dont_synthesize():
    """Ensure we don't synthesize a book when missing."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    # No book provided → should fail closed
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        book=None,
        session=session,
        levels=compute_levels(current_price=100.0),
    )
    
    assert gate.book_blocks is True
    assert gate.execute_action == "flat"
    # Ensure we didn't invent NAV or capacity
    assert any("snapshot missing" in r.lower() for r in gate.reasons)


# ============================================================================
# Risk veto tests
# ============================================================================

def test_risk_veto_missing_fails_closed():
    """Missing risk_veto → fail closed (flat for NEW risk)."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto=None,  # Missing!
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.risk_veto_blocks is True
    assert any("missing or invalid" in r.lower() for r in gate.reasons)


def test_risk_veto_invalid_decision_fails_closed():
    """Invalid risk_veto.decision → fail closed."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "UNKNOWN", "reason": "invalid"},
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.risk_veto_blocks is True


def test_risk_veto_veto_stays_flat():
    """VETO → stay flat, risk = 0."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    gate = gate_execution(
        policy_hint={"action": "long", "suggested_risk_pct": 0.01},
        risk_veto={"decision": "VETO", "reason": "Risk veto: high VaR", "missing": [], "risk_pct": None},
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.risk_veto_blocks is True
    assert gate.risk_veto_decision == "VETO"
    assert gate.final_risk_pct == 0.0
    assert any("veto" in r.lower() for r in gate.reasons)


def test_risk_veto_cut_with_null_risk_pct_flat():
    """CUT with null risk_pct → fail closed (flat)."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    gate = gate_execution(
        policy_hint={"action": "long", "suggested_risk_pct": 0.01},
        risk_veto={"decision": "CUT", "reason": "Size cut", "missing": ["risk_pct"], "risk_pct": None},
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.risk_veto_blocks is True
    assert gate.final_risk_pct == 0.0
    assert any("null/invalid risk_pct" in r.lower() for r in gate.reasons)


def test_risk_veto_cut_keeps_long_uses_risk_pct():
    """CUT with valid risk_pct → keep long if policy says long, use risk_veto.risk_pct."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    gate = gate_execution(
        policy_hint={"action": "long", "suggested_risk_pct": 0.01},
        risk_veto={"decision": "CUT", "reason": "Size cut to 0.5%", "missing": [], "risk_pct": 0.005},
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "long"
    assert gate.would_be_flat is False
    assert gate.risk_veto_blocks is False
    assert gate.risk_veto_decision == "CUT"
    assert gate.final_risk_pct == 0.005  # From risk_veto, not policy
    assert any("cut" in r.lower() for r in gate.reasons)


def test_risk_veto_cut_policy_flat_stays_flat():
    """CUT but policy is flat → stay flat (CUT doesn't force long)."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    gate = gate_execution(
        policy_hint={"action": "flat"},
        risk_veto={"decision": "CUT", "reason": "Size cut", "missing": [], "risk_pct": 0.005},
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True


def test_risk_veto_allow_applies_other_gates():
    """ALLOW → still apply clock/tape/memory gates."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    # ALLOW + policy long + all gates pass → long
    gate = gate_execution(
        policy_hint={"action": "long", "suggested_risk_pct": 0.01},
        risk_veto={"decision": "ALLOW", "reason": "Risk approved", "missing": [], "risk_pct": None},
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "long"
    assert gate.would_be_flat is False
    assert gate.risk_veto_decision == "ALLOW"
    assert gate.final_risk_pct == 0.01  # From policy


def test_risk_veto_allow_session_closed_flat():
    """ALLOW but session closed → flat (other gates still apply)."""
    sat = datetime(2026, 8, 16, 14, 0, tzinfo=US_EASTERN)
    session = get_session_state(sat)
    
    gate = gate_execution(
        policy_hint={"action": "long"},
        risk_veto={"decision": "ALLOW", "reason": "Risk approved", "missing": [], "risk_pct": None},
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "flat"
    assert gate.would_be_flat is True
    assert gate.session_blocks is True


def test_risk_veto_dont_parse_policy_rationale():
    """Don't infer veto by parsing policy_hint rationale text."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    session = get_session_state(mon_open)
    
    # Policy rationale mentions "veto" but risk_veto is ALLOW → should be long
    gate = gate_execution(
        policy_hint={
            "action": "long",
            "rationale": "Risk veto mentioned in text but this is ALLOW",
            "suggested_risk_pct": 0.01,
        },
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        session=session,
        levels=compute_levels(current_price=100.0),
        book=_VALID_BOOK,
    )
    assert gate.execute_action == "long"
    assert gate.would_be_flat is False


def test_timing_card_risk_veto_missing():
    """Timing card: missing risk_veto → not a trade."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "long"},
        risk_veto=None,  # Missing!
        current_price=150.0,
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is False
    assert card.risk_veto_blocks is True
    assert card.execute_action == "flat"
    assert card.final_risk_pct == 0.0


def test_timing_card_risk_veto_veto():
    """Timing card: VETO → not a trade."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "long", "suggested_risk_pct": 0.01},
        risk_veto={"decision": "VETO", "reason": "High VaR", "missing": [], "risk_pct": None},
        current_price=150.0,
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is False
    assert card.risk_veto_decision == "VETO"
    assert card.execute_action == "flat"
    assert card.final_risk_pct == 0.0


def test_timing_card_risk_veto_cut():
    """Timing card: CUT with valid risk_pct → now a trade (uses risk_veto.risk_pct)."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "long", "suggested_risk_pct": 0.01},
        risk_veto={"decision": "CUT", "reason": "Size to 0.3%", "missing": [], "risk_pct": 0.003},
        current_price=150.0,
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is True
    assert card.risk_veto_decision == "CUT"
    assert card.execute_action == "long"
    assert card.final_risk_pct == 0.003  # From risk_veto, not policy
    assert card.would_be_flat is False


def test_timing_card_risk_veto_allow():
    """Timing card: ALLOW → applies other gates, now a trade if all pass."""
    mon_open = datetime(2026, 8, 17, 10, 30, tzinfo=US_EASTERN)
    
    card = build_timing_card(
        "AAPL",
        policy_hint={"action": "long", "suggested_risk_pct": 0.01},
        risk_veto={"decision": "ALLOW", "reason": "Approved", "missing": [], "risk_pct": None},
        current_price=150.0,
        timestamp=mon_open,
        book=_VALID_BOOK,
    )
    
    assert card.now_a_trade is True
    assert card.risk_veto_decision == "ALLOW"
    assert card.execute_action == "long"
    assert card.final_risk_pct == 0.01  # From policy


if __name__ == "__main__":
    # Session clock
    test_weekend_closed()
    test_regular_hours_open()
    test_premarket_no_new_trades()
    test_after_hours_no_new_trades()
    test_holiday_closed()
    test_is_market_open_helpers()
    
    # Horizon
    test_explicit_session_mode()
    test_explicit_swing_mode()
    test_high_volatility_weak_trend_session()
    test_strong_trend_swing()
    test_high_score_swing()
    
    # Levels
    test_missing_price_tape_invalid()
    test_levels_from_policy_stop()
    test_session_tighter_stop()
    test_atr_fallback_stop()
    test_validate_tape_quality()
    
    # Gate
    test_policy_hint_flat_stays_flat()
    test_research_buy_policy_flat_conflict()
    test_memory_block_new_long()
    test_session_closed_blocks()
    test_missing_tape_blocks()
    test_all_gates_pass_allows_long()
    test_normalize_action()
    
    # Risk veto
    test_risk_veto_missing_fails_closed()
    test_risk_veto_invalid_decision_fails_closed()
    test_risk_veto_veto_stays_flat()
    test_risk_veto_cut_with_null_risk_pct_flat()
    test_risk_veto_cut_keeps_long_uses_risk_pct()
    test_risk_veto_cut_policy_flat_stays_flat()
    test_risk_veto_allow_applies_other_gates()
    test_risk_veto_allow_session_closed_flat()
    test_risk_veto_dont_parse_policy_rationale()
    
    # Timing card integration
    test_timing_card_weekend_not_a_trade()
    test_timing_card_open_market_with_tape()
    test_timing_card_policy_flat_not_a_trade()
    test_timing_card_missing_price_not_a_trade()
    test_timing_card_memory_block_not_a_trade()
    test_timing_card_session_vs_swing()
    test_timing_card_risk_veto_missing()
    test_timing_card_risk_veto_veto()
    test_timing_card_risk_veto_cut()
    test_timing_card_risk_veto_allow()
    
    # PM book tests
    test_book_ready_false_blocks()
    test_book_missing_blocks()
    test_book_nav_unknown_blocks()
    test_book_nav_null_blocks()
    test_book_capacity_flat_blocks()
    test_book_ready_with_cash_passes()
    test_book_ready_with_positions_passes()
    test_book_dont_synthesize()
    
    print("All trader timing tests passed.")
