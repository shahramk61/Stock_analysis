"""
Risk-based position sizing that wraps existing position_size_shares logic.
Returns 0 shares if vetoed or if price/stop/equity missing.
"""

from __future__ import annotations

from typing import Optional

from .gate import RiskDecision


def _position_size_shares(
    equity: float,
    risk_pct: float,
    price: float,
    stop_price: Optional[float] = None,
    min_shares: int = 0,
    max_notional_pct: float = 0.95,
) -> int:
    """
    Risk-based size capped by cash notional.
    Canonical source: backtest.policy.position_size_shares.
    Replicated here to avoid yfinance dependency at import time.
    """
    if equity <= 0 or risk_pct <= 0 or price <= 0:
        return 0
    if stop_price is not None and stop_price > 0 and stop_price < price:
        stop_dist = price - float(stop_price)
    else:
        stop_dist = price * 0.02
    stop_dist = max(stop_dist, price * 0.005)
    shares = int((equity * risk_pct) / stop_dist)
    max_shares = int((equity * max_notional_pct) / price)
    shares = min(shares, max_shares)
    if shares < 1:
        return 0
    if min_shares > 0:
        return max(min_shares, shares)
    return shares


def size_position(
    risk_decision: RiskDecision,
    equity: float,
    price: float,
    stop_price: Optional[float] = None,
    min_shares: int = 0,
    max_notional_pct: float = 0.95,
) -> int:
    """
    Risk-vetted position sizing.

    Returns 0 if:
      - risk_decision is VETO
      - risk_pct is 0
      - equity <= 0 or price <= 0

    Otherwise delegates to _position_size_shares with vetted risk_pct.
    """
    if risk_decision.vetoed():
        return 0

    risk_pct = risk_decision.risk_pct
    if risk_pct <= 0:
        return 0

    if equity <= 0 or price <= 0:
        return 0

    return _position_size_shares(
        equity=equity,
        risk_pct=risk_pct,
        price=price,
        stop_price=stop_price,
        min_shares=min_shares,
        max_notional_pct=max_notional_pct,
    )
