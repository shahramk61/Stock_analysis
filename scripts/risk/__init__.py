"""
Risk-owned trade vetting toolkit.

Risk owns size and the veto. Research BUY is not permission to size up.
Missing, non-point-in-time, or live-leaking data means VETO (fail closed).
"""

from .gate import (
    RiskDecision,
    VetoReason,
    vet_trade,
    VET_ALLOW,
    VET_CUT,
    VET_VETO,
)
from .sizing import size_position

__all__ = [
    "RiskDecision",
    "VetoReason",
    "vet_trade",
    "VET_ALLOW",
    "VET_CUT",
    "VET_VETO",
    "size_position",
]
