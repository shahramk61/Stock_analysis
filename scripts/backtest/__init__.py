"""
Backtesting package for the Stock Analysis agent.

Enables historical replay of the signal pipeline, scoring, Quantitative Analyst,
and decision logic to validate performance before live execution (e.g. broker/agentic APIs).

See the approved long-term plan (session plan.md) for phased approach.
Core goal: walk-forward, look-ahead-safe replay + simulation + metrics.
"""

from .data import load_historical_data, asof_snapshot
from .engine import Backtester
from .policy import default_policy, TradeSignal, position_size_shares
from .metrics import compute_metrics, summarize
from .memory import DecisionMemory, MemoryConfig

__all__ = [
    "load_historical_data",
    "asof_snapshot",
    "Backtester",
    "default_policy",
    "TradeSignal",
    "position_size_shares",
    "compute_metrics",
    "summarize",
    "DecisionMemory",
    "MemoryConfig",
]
