"""
Quant Fund Tools: Asof-safe measurement infrastructure for paper thematic fund.

This package provides the CIO-facing tools for Shahram's paper thematic fund:
1. Asof marks on every measurement
2. CIO conviction/score tracker (read-only ledger)
3. Honest five-year model support (unavailable if cannot compute)
4. Walk-forward of PM tickets with attribution

Quant owns whether the numbers are real. Does NOT pick themes or issue tickets.
"""

from scripts.quant.fund.asof_marks import AsofMark, mark_asof, validate_asof
from scripts.quant.fund.tracker import (
    CIOTracker,
    get_latest_tracker_state,
    get_tracker_time_series,
)
from scripts.quant.fund.five_year_model import (
    evaluate_five_year_model,
    FiveYearModelResult,
)
from scripts.quant.fund.ticket_replay import (
    replay_pm_tickets,
    Ticket,
    TicketReplayResult,
)

__all__ = [
    "AsofMark",
    "mark_asof",
    "validate_asof",
    "CIOTracker",
    "get_latest_tracker_state",
    "get_tracker_time_series",
    "evaluate_five_year_model",
    "FiveYearModelResult",
    "replay_pm_tickets",
    "Ticket",
    "TicketReplayResult",
]
