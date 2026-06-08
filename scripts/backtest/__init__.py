"""
Backtesting package for the Stock Analysis agent.

Enables historical replay of the signal pipeline, scoring, Quantitative Analyst,
and decision logic to validate performance before live execution (e.g. broker/agentic APIs).

See the approved long-term plan (session plan.md) for phased approach.
Core goal: walk-forward, look-ahead-safe replay + simulation + metrics.
"""

from .data import load_historical_data, asof_snapshot  # to be implemented
from .engine import Backtester  # to be implemented
from .policy import default_policy, TradeSignal  # to be implemented
from .metrics import compute_metrics, summarize  # to be implemented

__all__ = [
    "load_historical_data",
    "asof_snapshot",
    "Backtester",
    "default_policy",
    "TradeSignal",
    "compute_metrics",
    "summarize",
]
