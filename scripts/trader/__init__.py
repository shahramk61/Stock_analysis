"""
Trader-owned timing and execution tools for Stock Analysis desk.

This package provides a timing layer that answers (from existing facts only):
1. Is now actually a trade? (session clock / market open / tape present)
2. Session vs swing horizon
3. Entry / stop / exit levels (copied from pipeline/policy, never invented)
4. Would Execute / policy_hint actually be flat once timing + tape + memory are applied?

Trader does not run the book. Risk veto stands. No live broker. No invented prices.
If the thesis is good but the tape is wrong (missing/stale price, market closed, 
policy flat, memory block), stay flat and say why.
"""

from .session_clock import (
    MarketSession,
    SessionState,
    is_market_open,
    get_session_state,
    should_allow_new_trades,
)
from .horizon import (
    choose_horizon,
    Horizon,
)
from .levels import (
    TradeLevels,
    compute_levels,
)
from .gate import (
    ExecuteGate,
    gate_execution,
)
from .timing import (
    TimingCard,
    build_timing_card,
)

__all__ = [
    "MarketSession",
    "SessionState",
    "is_market_open",
    "get_session_state",
    "should_allow_new_trades",
    "choose_horizon",
    "Horizon",
    "TradeLevels",
    "compute_levels",
    "ExecuteGate",
    "gate_execution",
    "TimingCard",
    "build_timing_card",
]
