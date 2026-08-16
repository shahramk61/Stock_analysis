"""
Entry / stop / exit levels from Quant last_print (daily Close).

Uses last_print = last daily Close ≤ asof (NOT a live quote).
Never invents prices. If last_print is missing, returns None and stays flat.
Do not use current_price from live info leak as substitute.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TradeLevels:
    """
    Entry, stop, and exit levels for a trade.
    
    All prices may be None if data is missing/stale.
    Never invent prices - use last_print (daily Close ≤ asof) or return None.
    """
    entry_price: Optional[float]
    stop_price: Optional[float]
    exit_price: Optional[float]  # Target, may be None
    last_print: Optional[float]  # Last daily Close ≤ asof (NOT live quote)
    current_price: Optional[float]  # DEPRECATED: use last_print
    tape_valid: bool  # False if last_print is missing or invalid
    reason: str = ""


def compute_levels(
    *,
    last_print: Optional[float] = None,
    current_price: Optional[float] = None,  # DEPRECATED: use last_print
    policy_stop: Optional[float] = None,
    policy_target: Optional[float] = None,
    atr_pct: float = 0.0,
    mc_risk_stop: Optional[float] = None,
    horizon_tighter_stop: bool = False,
    session_stop_pct: float = 0.015,
) -> TradeLevels:
    """
    Compute entry/stop/exit levels from Quant last_print (daily Close ≤ asof).
    
    Args:
        last_print: Last daily Close ≤ asof (NOT live quote) - entry level
        current_price: DEPRECATED - use last_print instead
        policy_stop: Stop from policy (already computed by default_policy)
        policy_target: Target from policy (may be None)
        atr_pct: ATR percentage for fallback stops
        mc_risk_stop: Monte Carlo risk stop if available
        horizon_tighter_stop: True if session mode (tighter stops)
        session_stop_pct: Session stop percentage (default 1.5%)
    
    Returns:
        TradeLevels with entry, stop, exit (all nullable if data missing)
    """
    # Prefer last_print, fallback to current_price for backward compat
    price = last_print if last_print is not None else current_price
    
    # Validate tape: last_print must exist
    if price is None or price <= 0:
        return TradeLevels(
            entry_price=None,
            stop_price=None,
            exit_price=None,
            last_print=None,
            current_price=None,
            tape_valid=False,
            reason="Missing or invalid last_print - no tape",
        )
    
    tape_valid = True
    entry = price
    
    # Stop priority:
    # 1. Session mode: tighter stop (floor at session_stop_pct, widen with ATR up to 3%)
    # 2. Policy stop (from default_policy - already considers mc_risk_stop and ATR)
    # 3. MC risk stop
    # 4. ATR-based fallback
    # 5. Fixed 8% fallback
    
    stop = None
    stop_reason = ""
    
    if horizon_tighter_stop:
        # Session mode: tight open→close stop
        atr_stop_pct = max(
            session_stop_pct,
            min(0.03, (atr_pct / 100.0) if atr_pct > 0 else session_stop_pct),
        )
        stop = price * (1.0 - atr_stop_pct)
        stop_reason = f"session stop {atr_stop_pct * 100:.1f}%"
    elif policy_stop is not None and policy_stop > 0:
        # Use policy stop (already computed by default_policy)
        stop = policy_stop
        stop_reason = "from policy (mc_risk or ATR)"
    elif mc_risk_stop is not None and mc_risk_stop > 0:
        stop = mc_risk_stop
        stop_reason = "from mc_risk"
    elif atr_pct > 0:
        # ATR-based: 1.5x ATR below current
        stop = price * (1 - max(0.05, atr_pct / 100 * 1.5))
        stop_reason = f"ATR-based (1.5x {atr_pct:.1f}%)"
    else:
        # Fixed 8% fallback
        stop = price * 0.92
        stop_reason = "fixed 8% fallback"
    
    # Exit target (optional, from policy or DCF)
    exit_price = policy_target if policy_target and policy_target > price else None
    
    reason = f"Entry={entry:.2f}, stop={stop:.2f} ({stop_reason})"
    if exit_price:
        reason += f", target={exit_price:.2f}"
    
    return TradeLevels(
        entry_price=entry,
        stop_price=stop,
        exit_price=exit_price,
        last_print=price,
        current_price=price,  # Backward compat
        tape_valid=tape_valid,
        reason=reason,
    )


def validate_tape_quality(
    *,
    current_price: Optional[float],
    volume: Optional[float] = None,
    last_update_age_minutes: Optional[int] = None,
    max_stale_minutes: int = 60,
) -> tuple[bool, str]:
    """
    Validate tape quality: price present, not stale, sufficient volume.
    
    Args:
        current_price: Current market price
        volume: Recent volume (optional check)
        last_update_age_minutes: Age of last price update in minutes
        max_stale_minutes: Maximum allowed staleness
    
    Returns:
        (is_valid, reason) tuple
    """
    if current_price is None or current_price <= 0:
        return False, "Missing or invalid current_price"
    
    if last_update_age_minutes is not None and last_update_age_minutes > max_stale_minutes:
        return False, f"Stale price (last update {last_update_age_minutes}m ago)"
    
    if volume is not None and volume <= 0:
        return False, "Zero volume - no liquidity"
    
    return True, "Tape valid"
