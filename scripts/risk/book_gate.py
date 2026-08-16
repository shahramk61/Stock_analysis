"""
Fund-level book constraint gate for thematic paper fund.

This module validates trading tickets (BUY/ADD, TRIM/SELL, HOLD) against
fund-level constraints: liquidity, concentration, cash, name/theme purity.

It does NOT veto based on VaR, CVaR, death cross, or other stock-level signals.
Those belong to Theme Research and CIO approval.

Decision types:
  - ALLOW: Ticket passes all constraints
  - BLOCK: Ticket violates hard constraints (missing data, concentration, cash, liquidity)
  - FLAG: Ticket (usually TRIM/SELL) would strand the book but is not blocked

Fail-closed philosophy: Missing NAV, missing asof marks, or missing liquidity
data for ADDs result in BLOCK, not invented numbers.

Updated: August 2026 - Replaces daily VaR flatten model
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from . import limits


class Position:
    """Represents a single position in the book."""
    
    def __init__(
        self,
        ticker: str,
        weight_pct: float = 0.0,
        notional: float = 0.0,
        sector: Optional[str] = None,
        theme: Optional[str] = None,
        liquidity_adv: Optional[float] = None,
    ):
        self.ticker = ticker.upper()
        self.weight_pct = weight_pct
        self.notional = notional
        self.sector = sector
        self.theme = theme
        self.liquidity_adv = liquidity_adv


class Book:
    """Represents the current portfolio book."""
    
    def __init__(
        self,
        nav: Optional[float] = None,
        cash: Optional[float] = None,
        positions: Optional[List[Position]] = None,
        asof: Optional[str] = None,
    ):
        self.nav = nav
        self.cash = cash
        self.positions = positions or []
        self.asof = asof
    
    @property
    def cash_pct(self) -> Optional[float]:
        """Cash as percentage of NAV."""
        if self.nav is None or self.nav <= 0 or self.cash is None:
            return None
        return (self.cash / self.nav) * 100.0
    
    @property
    def num_names(self) -> int:
        """Number of positions in the book."""
        return len(self.positions)
    
    def get_position(self, ticker: str) -> Optional[Position]:
        """Find a position by ticker."""
        ticker_upper = ticker.upper()
        for pos in self.positions:
            if pos.ticker == ticker_upper:
                return pos
        return None
    
    def sector_theme_exposure(self, sector_or_theme: str) -> float:
        """Total weight % for a given sector or theme."""
        total = 0.0
        for pos in self.positions:
            if pos.sector == sector_or_theme or pos.theme == sector_or_theme:
                total += pos.weight_pct
        return total


class RiskDecision:
    """
    Result of book constraint validation.
    
    Attributes:
        decision: "ALLOW" | "BLOCK" | "FLAG"
        reason: Primary human-readable reason
        reasons: List of all constraint violations/warnings
        missing: List of missing data fields that caused fail-closed
        ticket_type: "BUY" | "ADD" | "TRIM" | "SELL" | "HOLD"
        ticker: Stock ticker
        asof: As-of date (YYYY-MM-DD)
        cio_approved: Whether this is a CIO-approved hold
    """
    
    def __init__(
        self,
        decision: str,
        reason: str,
        ticker: str,
        ticket_type: str,
        asof: Optional[str] = None,
        reasons: Optional[List[str]] = None,
        missing: Optional[List[str]] = None,
        cio_approved: bool = False,
    ):
        self.decision = decision.upper()
        self.reason = reason
        self.reasons = reasons or []
        self.missing = missing or []
        self.ticker = ticker.upper()
        self.ticket_type = ticket_type.upper()
        self.asof = asof
        self.cio_approved = cio_approved
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "decision": self.decision,
            "reason": self.reason,
            "reasons": self.reasons,
            "missing": self.missing,
            "ticket": self.ticket_type,
            "ticker": self.ticker,
            "asof": self.asof,
            "cio_approved": self.cio_approved,
        }
    
    def to_veto_object(self) -> Dict[str, Any]:
        """
        Convert to legacy veto object format for backward compatibility.
        Maps ALLOW/BLOCK/FLAG to the structured format Trader/PM expects.
        """
        return {
            "action": self.decision,  # ALLOW | BLOCK | FLAG
            "ticker": self.ticker,
            "ticket_type": self.ticket_type,
            "reason": self.reason,
            "details": {
                "reasons": self.reasons,
                "missing": self.missing,
                "asof": self.asof,
                "cio_approved": self.cio_approved,
            }
        }


def check_book_constraints(
    ticker: str,
    ticket_type: str,
    book: Book,
    proposed_weight_pct: Optional[float] = None,
    proposed_notional: Optional[float] = None,
    sector: Optional[str] = None,
    theme: Optional[str] = None,
    liquidity_adv: Optional[float] = None,
    cio_approved: bool = False,
    correlation_data: Optional[Dict[str, float]] = None,
) -> RiskDecision:
    """
    Validate a proposed ticket against fund-level book constraints.
    
    Args:
        ticker: Stock ticker symbol
        ticket_type: "BUY", "ADD", "TRIM", "SELL", or "HOLD"
        book: Current book state (NAV, cash, positions, asof)
        proposed_weight_pct: Proposed position weight % (for BUY/ADD)
        proposed_notional: Proposed position notional $ (for BUY/ADD)
        sector: Sector tag for the position
        theme: Theme tag for the position (required for theme purity)
        liquidity_adv: Average daily volume $ for liquidity checks
        cio_approved: Whether this HOLD is CIO-approved (bypasses VaR blocks)
        correlation_data: Dict of ticker -> correlation for factor cluster checks
    
    Returns:
        RiskDecision with ALLOW, BLOCK, or FLAG
    """
    ticker = ticker.upper()
    ticket_type = ticket_type.upper()
    
    reasons: List[str] = []
    missing: List[str] = []
    
    # 1. Fail-closed on missing NAV or asof
    if book.nav is None or book.nav <= 0:
        missing.append("NAV")
        return RiskDecision(
            decision="BLOCK",
            reason="Missing or invalid NAV - fail closed",
            ticker=ticker,
            ticket_type=ticket_type,
            asof=book.asof,
            reasons=["NAV missing or <= 0"],
            missing=missing,
            cio_approved=cio_approved,
        )
    
    if book.asof is None or book.asof == "":
        missing.append("asof")
        return RiskDecision(
            decision="BLOCK",
            reason="Missing asof date - fail closed",
            ticker=ticker,
            ticket_type=ticket_type,
            asof=book.asof,
            reasons=["asof date missing"],
            missing=missing,
            cio_approved=cio_approved,
        )
    
    # 2. HOLD logic: Do NOT block for VaR, CVaR, Bear, death cross
    # CIO-approved holds especially should pass through
    if ticket_type == "HOLD":
        if cio_approved:
            return RiskDecision(
                decision="ALLOW",
                reason="CIO-approved HOLD - book constraints not blocking",
                ticker=ticker,
                ticket_type=ticket_type,
                asof=book.asof,
                reasons=["CIO-approved HOLD passes through"],
                missing=missing,
                cio_approved=cio_approved,
            )
        else:
            # Regular hold - still don't block on VaR/regime
            return RiskDecision(
                decision="ALLOW",
                reason="HOLD not subject to VaR/regime gates",
                ticker=ticker,
                ticket_type=ticket_type,
                asof=book.asof,
                reasons=["HOLD allowed under book constraint model"],
                missing=missing,
                cio_approved=cio_approved,
            )
    
    # 3. BUY/ADD constraint checks
    if ticket_type in ("BUY", "ADD"):
        return _check_buy_add_constraints(
            ticker=ticker,
            ticket_type=ticket_type,
            book=book,
            proposed_weight_pct=proposed_weight_pct,
            proposed_notional=proposed_notional,
            sector=sector,
            theme=theme,
            liquidity_adv=liquidity_adv,
            cio_approved=cio_approved,
            correlation_data=correlation_data,
            reasons=reasons,
            missing=missing,
        )
    
    # 4. TRIM/SELL constraint checks
    if ticket_type in ("TRIM", "SELL"):
        return _check_trim_sell_constraints(
            ticker=ticker,
            ticket_type=ticket_type,
            book=book,
            proposed_weight_pct=proposed_weight_pct,
            reasons=reasons,
            missing=missing,
            cio_approved=cio_approved,
        )
    
    # Unknown ticket type
    return RiskDecision(
        decision="BLOCK",
        reason=f"Unknown ticket type: {ticket_type}",
        ticker=ticker,
        ticket_type=ticket_type,
        asof=book.asof,
        reasons=[f"Unrecognized ticket_type: {ticket_type}"],
        missing=missing,
        cio_approved=cio_approved,
    )


def _check_buy_add_constraints(
    ticker: str,
    ticket_type: str,
    book: Book,
    proposed_weight_pct: Optional[float],
    proposed_notional: Optional[float],
    sector: Optional[str],
    theme: Optional[str],
    liquidity_adv: Optional[float],
    cio_approved: bool,
    correlation_data: Optional[Dict[str, float]],
    reasons: List[str],
    missing: List[str],
) -> RiskDecision:
    """Check constraints for BUY/ADD tickets."""
    
    # Calculate proposed weight if not provided
    if proposed_weight_pct is None:
        if proposed_notional is not None and book.nav and book.nav > 0:
            proposed_weight_pct = (proposed_notional / book.nav) * 100.0
        else:
            missing.append("proposed_weight_pct")
            reasons.append("Cannot determine proposed position weight")
    
    # Theme purity check
    if limits.REQUIRE_THEME_TAG:
        if theme is None or theme == "":
            missing.append("theme")
            reasons.append("Theme tag required for purity - missing")
    
    # Liquidity check - fail closed on missing ADV for ADD
    existing_pos = book.get_position(ticker)
    is_first_add = existing_pos is None
    
    if not is_first_add:  # This is an ADD to existing position
        if liquidity_adv is None:
            missing.append("liquidity_adv")
            reasons.append("Liquidity ADV required for ADD - fail closed")
    elif liquidity_adv is None:
        # Even for first BUY, we should have liquidity data
        missing.append("liquidity_adv")
        reasons.append("Liquidity ADV required for BUY - fail closed")
    
    # If we have liquidity data, check it
    if proposed_notional is not None and liquidity_adv is not None:
        max_position_for_liquidity = liquidity_adv / limits.MIN_LIQUIDITY_ADV_MULTIPLIER
        if proposed_notional > max_position_for_liquidity:
            reasons.append(
                f"Position ${proposed_notional:,.0f} exceeds liquidity limit "
                f"${max_position_for_liquidity:,.0f} (ADV/20)"
            )
    
    # Post-trade checks
    if proposed_weight_pct is not None:
        # Single name concentration
        if proposed_weight_pct > limits.MAX_SINGLE_NAME_PCT:
            reasons.append(
                f"Position weight {proposed_weight_pct:.1f}% exceeds "
                f"single name limit {limits.MAX_SINGLE_NAME_PCT}%"
            )
        
        # Sector/theme concentration
        if sector or theme:
            sector_theme_key = theme or sector
            if sector_theme_key:
                current_sector_theme = book.sector_theme_exposure(sector_theme_key)
                post_trade_sector_theme = current_sector_theme + proposed_weight_pct
                if post_trade_sector_theme > limits.MAX_SECTOR_THEME_PCT:
                    reasons.append(
                        f"Sector/theme '{sector_theme_key}' exposure {post_trade_sector_theme:.1f}% "
                        f"exceeds limit {limits.MAX_SECTOR_THEME_PCT}%"
                    )
        
        # Cash constraint
        post_trade_cash_pct = book.cash_pct
        if post_trade_cash_pct is not None:
            # Approximate post-trade cash (assuming we're spending cash to buy)
            cash_used = (proposed_weight_pct / 100.0) * book.nav if book.nav else 0
            post_cash = (book.cash or 0) - cash_used
            post_trade_cash_pct = (post_cash / book.nav) * 100.0 if book.nav and book.nav > 0 else None
            
            if post_trade_cash_pct is not None and post_trade_cash_pct < limits.MIN_CASH_PCT:
                reasons.append(
                    f"Post-trade cash {post_trade_cash_pct:.1f}% below minimum {limits.MIN_CASH_PCT}%"
                )
    
    # Name count check
    will_add_new_name = book.get_position(ticker) is None
    post_trade_names = book.num_names + (1 if will_add_new_name else 0)
    if post_trade_names > limits.MAX_NAMES:
        reasons.append(
            f"Post-trade name count {post_trade_names} exceeds limit {limits.MAX_NAMES}"
        )
    
    # Factor cluster check (only for multi-name ADD)
    # "First add" exception means: the book is currently empty (no positions at all)
    # "Multi-name ADD" means: the book already has at least one position
    is_book_empty = book.num_names == 0
    
    if limits.REQUIRE_CORR_FOR_MULTI_NAME_ADD and not is_book_empty:
        # Book has positions, so this is a multi-name add
        if correlation_data is None:
            missing.append("correlation_data")
            reasons.append("Correlation data required for multi-name ADD - fail closed")
        elif correlation_data is not None and proposed_weight_pct is not None:
            # Check factor cluster exposure
            cluster_exposure = proposed_weight_pct
            for pos in book.positions:
                corr = correlation_data.get(pos.ticker, 0.0)
                if abs(corr) > 0.5:  # High correlation threshold
                    cluster_exposure += pos.weight_pct
            
            if cluster_exposure > limits.MAX_FACTOR_CLUSTER_PCT:
                reasons.append(
                    f"Factor cluster exposure {cluster_exposure:.1f}% exceeds "
                    f"limit {limits.MAX_FACTOR_CLUSTER_PCT}%"
                )
    
    # Decision logic
    if len(missing) > 0 or len(reasons) > 0:
        primary_reason = reasons[0] if reasons else f"Missing data: {', '.join(missing)}"
        return RiskDecision(
            decision="BLOCK",
            reason=primary_reason,
            ticker=ticker,
            ticket_type=ticket_type,
            asof=book.asof,
            reasons=reasons,
            missing=missing,
            cio_approved=cio_approved,
        )
    
    return RiskDecision(
        decision="ALLOW",
        reason="All book constraints satisfied",
        ticker=ticker,
        ticket_type=ticket_type,
        asof=book.asof,
        reasons=["BUY/ADD passes all constraints"],
        missing=missing,
        cio_approved=cio_approved,
    )


def _check_trim_sell_constraints(
    ticker: str,
    ticket_type: str,
    book: Book,
    proposed_weight_pct: Optional[float],
    reasons: List[str],
    missing: List[str],
    cio_approved: bool,
) -> RiskDecision:
    """
    Check constraints for TRIM/SELL tickets.
    
    We ALLOW these by default but FLAG if the exit would strand the book:
    - Cash falls below floor
    - Name count becomes too low
    - Creates orphan theme
    - Liquidity hole
    """
    
    flags: List[str] = []
    
    existing_pos = book.get_position(ticker)
    if existing_pos is None:
        return RiskDecision(
            decision="ALLOW",
            reason="Cannot TRIM/SELL position not in book",
            ticker=ticker,
            ticket_type=ticket_type,
            asof=book.asof,
            reasons=["Position not found in book"],
            missing=missing,
            cio_approved=cio_approved,
        )
    
    # Estimate post-trade state
    if ticket_type == "SELL":
        # Full exit
        post_trade_names = book.num_names - 1
        cash_returned_pct = existing_pos.weight_pct
    else:  # TRIM
        # Partial exit
        post_trade_names = book.num_names
        if proposed_weight_pct is not None:
            # Trim to proposed_weight_pct
            cash_returned_pct = existing_pos.weight_pct - proposed_weight_pct
        else:
            # Assume 50% trim if not specified
            cash_returned_pct = existing_pos.weight_pct * 0.5
    
    # Check if name count becomes too low
    if post_trade_names < limits.STRANDED_MIN_NAMES:
        flags.append(
            f"Post-trade name count {post_trade_names} below minimum {limits.STRANDED_MIN_NAMES} "
            "(stranded book)"
        )
    
    # Check if cash would be stranded (though typically SELL adds cash, so this is unusual)
    # More relevant: check if remaining book would be illiquid
    if book.cash_pct is not None:
        post_trade_cash_pct = book.cash_pct + cash_returned_pct
        if post_trade_cash_pct < limits.STRANDED_CASH_FLOOR_PCT:
            flags.append(
                f"Post-trade cash {post_trade_cash_pct:.1f}% below stranded floor "
                f"{limits.STRANDED_CASH_FLOOR_PCT}%"
            )
    
    # Theme/sector orphaning check
    if existing_pos.theme or existing_pos.sector:
        sector_theme_key = existing_pos.theme or existing_pos.sector
        if sector_theme_key:
            # Count how many other positions share this theme/sector
            theme_peers = [
                p for p in book.positions
                if p.ticker != ticker and (p.theme == sector_theme_key or p.sector == sector_theme_key)
            ]
            if len(theme_peers) == 0 and ticket_type == "SELL":
                flags.append(
                    f"SELL would orphan theme/sector '{sector_theme_key}' (no other positions)"
                )
    
    # Liquidity hole check
    if limits.STRANDED_LIQUIDITY_CHECK and ticket_type == "SELL":
        # Check if remaining positions have adequate liquidity
        remaining_positions = [p for p in book.positions if p.ticker != ticker]
        illiquid_count = sum(1 for p in remaining_positions if p.liquidity_adv is None)
        if illiquid_count > 0 and len(remaining_positions) > 0:
            flags.append(
                f"SELL creates liquidity hole: {illiquid_count}/{len(remaining_positions)} "
                "remaining positions lack liquidity data"
            )
    
    # Decision
    if flags:
        return RiskDecision(
            decision="FLAG",
            reason=flags[0],
            ticker=ticker,
            ticket_type=ticket_type,
            asof=book.asof,
            reasons=flags,
            missing=missing,
            cio_approved=cio_approved,
        )
    
    return RiskDecision(
        decision="ALLOW",
        reason="TRIM/SELL does not strand the book",
        ticker=ticker,
        ticket_type=ticket_type,
        asof=book.asof,
        reasons=["TRIM/SELL passes strand checks"],
        missing=missing,
        cio_approved=cio_approved,
    )
