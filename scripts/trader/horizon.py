"""
Horizon chooser: session vs swing.

Uses existing execution_mode / ATR / ADX / score from policy.
Does not turn forecasts on. Path C multi-horizon entry stays opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class Horizon(str, Enum):
    """Trading horizon."""
    SESSION = "session"  # Same-day open→close
    SWING = "swing"      # Multi-day holds


@dataclass
class HorizonChoice:
    """Result of horizon selection."""
    horizon: Horizon
    reason: str
    tighter_stop: bool  # True if session (tighter stops)
    days: Optional[int] = None  # Expected holding period (1 for session, N for swing)


def choose_horizon(
    *,
    execution_mode: Optional[str] = None,
    overall_score: float = 50.0,
    atr_pct: float = 0.0,
    adx: float = 0.0,
    signals: Optional[Dict[str, Any]] = None,
) -> HorizonChoice:
    """
    Choose session vs swing horizon based on existing policy inputs.
    
    Args:
        execution_mode: Explicit mode from caller ("session" or "swing")
        overall_score: Overall score (higher scores may favor longer holds)
        atr_pct: ATR percentage (higher volatility may favor session)
        adx: ADX value (trend strength; strong trends favor swing)
        signals: Full signals dict (may contain multi_h for swing horizon days)
    
    Returns:
        HorizonChoice with horizon, reason, and stop tightness flag
    """
    # Explicit execution_mode wins
    if execution_mode and str(execution_mode).lower() == "session":
        return HorizonChoice(
            horizon=Horizon.SESSION,
            reason="Explicit session mode requested",
            tighter_stop=True,
            days=1,
        )
    
    if execution_mode and str(execution_mode).lower() == "swing":
        # Check if multi_h signals suggest a horizon
        days = _extract_swing_days(signals)
        return HorizonChoice(
            horizon=Horizon.SWING,
            reason="Explicit swing mode requested",
            tighter_stop=False,
            days=days,
        )
    
    # Default logic: session if high volatility + weak trend + mid score
    # Otherwise swing
    
    # High ATR (>4%) suggests intraday volatility → session may be safer
    high_volatility = atr_pct > 4.0
    
    # Strong trend (ADX >= 25) suggests holding through swings → swing
    strong_trend = adx >= 25.0
    
    # Higher scores (>=60) suggest conviction → swing
    high_conviction = overall_score >= 60.0
    
    # Session criteria: high vol + no strong trend + mid-range score
    if high_volatility and not strong_trend and 50 <= overall_score < 60:
        return HorizonChoice(
            horizon=Horizon.SESSION,
            reason=f"High volatility (ATR {atr_pct:.1f}%), weak trend (ADX {adx:.1f}) → session",
            tighter_stop=True,
            days=1,
        )
    
    # Swing (default): multi-day hold
    days = _extract_swing_days(signals)
    reasons = []
    if strong_trend:
        reasons.append(f"strong trend (ADX {adx:.1f})")
    if high_conviction:
        reasons.append(f"high score ({overall_score:.1f})")
    if not high_volatility:
        reasons.append(f"moderate volatility (ATR {atr_pct:.1f}%)")
    
    reason_str = ", ".join(reasons) if reasons else "default multi-day hold"
    
    return HorizonChoice(
        horizon=Horizon.SWING,
        reason=f"Swing: {reason_str}",
        tighter_stop=False,
        days=days,
    )


def _extract_swing_days(signals: Optional[Dict[str, Any]]) -> Optional[int]:
    """
    Extract horizon days from multi_horizon forecasts if present.
    Returns first bullish horizon or None.
    """
    if not signals or not isinstance(signals, dict):
        return None
    
    multi = signals.get("multi_horizon_forecasts") or signals.get("multi_h")
    if not isinstance(multi, dict):
        return None
    
    horizons = multi.get("horizons")
    if not isinstance(horizons, dict):
        return None
    
    # Check 5d, 10d, 15d, 20d in order
    for h in ["5d", "10d", "15d", "20d"]:
        hd = horizons.get(h)
        if isinstance(hd, dict):
            direction = str(hd.get("direction", "")).lower()
            if "bull" in direction:
                try:
                    return int(h.replace("d", ""))
                except (ValueError, TypeError):
                    pass
    
    return None
