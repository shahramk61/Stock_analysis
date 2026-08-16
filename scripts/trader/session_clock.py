"""
Session clock for US equities (America/New_York).

Regular hours: 9:30 AM - 4:00 PM ET
Pre-market: 4:00 AM - 9:30 AM ET (exists but not enabled for new risk)
After-hours: 4:00 PM - 8:00 PM ET (exists but not enabled for new risk)

Weekend / holiday handling: closed market → force flat for new risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, date
from enum import Enum
from typing import Optional
import zoneinfo


US_EASTERN = zoneinfo.ZoneInfo("America/New_York")

# US market holidays 2026 (NYSE observed)
# Note: when a holiday falls on weekend, observed day may shift
US_MARKET_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # Martin Luther King Jr. Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}


class SessionState(str, Enum):
    """Market session state."""
    CLOSED_WEEKEND = "closed_weekend"
    CLOSED_HOLIDAY = "closed_holiday"
    CLOSED_AFTER_HOURS = "closed_after_hours"
    PRE_MARKET = "pre_market"
    REGULAR_HOURS = "regular_hours"
    AFTER_HOURS = "after_hours"


@dataclass
class MarketSession:
    """Market session status at a given time."""
    state: SessionState
    is_open: bool  # True only if REGULAR_HOURS
    allows_new_trades: bool  # True only if REGULAR_HOURS (not pre/after for new risk)
    timestamp: datetime
    reason: str = ""


def is_weekend(dt: datetime) -> bool:
    """Check if date is Saturday (5) or Sunday (6)."""
    return dt.weekday() in (5, 6)


def is_holiday(dt: datetime) -> bool:
    """Check if date is a US market holiday."""
    return dt.date() in US_MARKET_HOLIDAYS_2026


def get_session_state(
    dt: Optional[datetime] = None,
    *,
    tz: zoneinfo.ZoneInfo = US_EASTERN,
) -> MarketSession:
    """
    Determine market session state for US equities.
    
    Args:
        dt: Datetime to check (defaults to now in US/Eastern)
        tz: Timezone (defaults to America/New_York)
    
    Returns:
        MarketSession with state, is_open, allows_new_trades
    """
    if dt is None:
        dt = datetime.now(tz)
    elif dt.tzinfo is None:
        # Assume ET if naive
        dt = dt.replace(tzinfo=tz)
    else:
        # Convert to ET
        dt = dt.astimezone(tz)
    
    # Weekend check
    if is_weekend(dt):
        return MarketSession(
            state=SessionState.CLOSED_WEEKEND,
            is_open=False,
            allows_new_trades=False,
            timestamp=dt,
            reason=f"{dt.strftime('%A')} - market closed",
        )
    
    # Holiday check
    if is_holiday(dt):
        return MarketSession(
            state=SessionState.CLOSED_HOLIDAY,
            is_open=False,
            allows_new_trades=False,
            timestamp=dt,
            reason=f"Holiday {dt.date()} - market closed",
        )
    
    # Time-of-day checks (ET)
    current_time = dt.time()
    
    # Regular hours: 9:30 AM - 4:00 PM ET
    market_open = time(9, 30)
    market_close = time(16, 0)
    
    if market_open <= current_time < market_close:
        return MarketSession(
            state=SessionState.REGULAR_HOURS,
            is_open=True,
            allows_new_trades=True,
            timestamp=dt,
            reason="Regular trading hours",
        )
    
    # Pre-market: 4:00 AM - 9:30 AM ET
    pre_market_start = time(4, 0)
    if pre_market_start <= current_time < market_open:
        return MarketSession(
            state=SessionState.PRE_MARKET,
            is_open=False,
            allows_new_trades=False,
            timestamp=dt,
            reason="Pre-market (no new risk)",
        )
    
    # After-hours: 4:00 PM - 8:00 PM ET
    after_hours_end = time(20, 0)
    if market_close <= current_time < after_hours_end:
        return MarketSession(
            state=SessionState.AFTER_HOURS,
            is_open=False,
            allows_new_trades=False,
            timestamp=dt,
            reason="After-hours (no new risk)",
        )
    
    # Otherwise closed (late night)
    return MarketSession(
        state=SessionState.CLOSED_AFTER_HOURS,
        is_open=False,
        allows_new_trades=False,
        timestamp=dt,
        reason="Market closed (late night / early morning)",
    )


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """Quick check: is regular cash session open right now?"""
    session = get_session_state(dt)
    return session.is_open


def should_allow_new_trades(dt: Optional[datetime] = None) -> bool:
    """
    Should new risk be allowed at this time?
    
    Returns True only during regular hours (not pre-market, after-hours, weekends, holidays).
    This is the gate for entering new positions.
    """
    session = get_session_state(dt)
    return session.allows_new_trades
