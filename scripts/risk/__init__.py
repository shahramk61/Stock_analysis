"""
Risk management for Shahram's thematic paper fund.

Book constraint model (August 2026): fund-level constraints on liquidity,
concentration, cash, name/theme purity. Daily VaR flatten is retired.

Main exports:
  - check_book_constraints: Validate tickets against book constraints
  - Book, Position, RiskDecision: Core data structures
  - limits module: Concentration constants
"""

from .book_gate import (
    Book,
    Position,
    RiskDecision,
    check_book_constraints,
)
from . import limits

__all__ = [
    "Book",
    "Position",
    "RiskDecision",
    "check_book_constraints",
    "limits",
]
