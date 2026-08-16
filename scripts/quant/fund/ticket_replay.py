"""
PM Ticket Walk-Forward Replay for Quant fund tools.

Walk-forward replay of PM-issued tickets: buy / add / trim / sell / rebalance.
Tracks paper book (positions, cash, weights) and computes attribution after asof.

Does NOT create tickets. Does NOT change ticket actions. Does NOT drop names.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd


class TicketAction(str, Enum):
    """PM ticket action types."""
    BUY = "buy"
    ADD = "add"
    TRIM = "trim"
    SELL = "sell"
    REBALANCE = "rebalance"


@dataclass
class Ticket:
    """
    A PM-issued ticket.
    
    Quant does not create tickets - they are input from PM.
    """
    
    date: date
    ticker: str
    action: TicketAction
    qty: Optional[float] = None  # Shares (for buy/add/trim/sell)
    weight: Optional[float] = None  # Target weight (for rebalance)
    limit: Optional[float] = None  # Limit price (optional)
    
    def __post_init__(self):
        """Validate ticket fields."""
        if self.action in (TicketAction.BUY, TicketAction.ADD, TicketAction.TRIM, TicketAction.SELL):
            if self.qty is None and self.weight is None:
                raise ValueError(f"{self.action} ticket requires qty or weight")
        if self.action == TicketAction.REBALANCE:
            if self.weight is None:
                raise ValueError("rebalance ticket requires weight")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": str(self.date),
            "ticker": self.ticker,
            "action": self.action.value,
            "qty": self.qty,
            "weight": self.weight,
            "limit": self.limit,
        }


@dataclass
class TicketFill:
    """
    Record of a ticket fill.
    
    Fill happens on/after ticket date, using last_print = Close <= asof (or next open).
    If no print available, ticket cannot fill (marked unfilled, no invented price).
    """
    
    ticket: Ticket
    filled: bool
    fill_date: Optional[date] = None
    fill_price: Optional[float] = None
    fill_qty: Optional[float] = None
    unfilled_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ticket": self.ticket.to_dict(),
            "filled": self.filled,
            "fill_date": str(self.fill_date) if self.fill_date else None,
            "fill_price": self.fill_price,
            "fill_qty": self.fill_qty,
            "unfilled_reason": self.unfilled_reason,
        }


@dataclass
class Position:
    """A position in the paper book."""
    
    ticker: str
    qty: float
    avg_cost: float
    
    @property
    def cost_basis(self) -> float:
        """Total cost basis of the position."""
        return self.qty * self.avg_cost
    
    def market_value(self, price: float) -> float:
        """Market value of the position at a given price."""
        return self.qty * price
    
    def unrealized_pnl(self, price: float) -> float:
        """Unrealized PnL at a given price."""
        return (price - self.avg_cost) * self.qty
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ticker": self.ticker,
            "qty": round(self.qty, 6),
            "avg_cost": round(self.avg_cost, 2),
            "cost_basis": round(self.cost_basis, 2),
        }


@dataclass
class PaperBook:
    """
    Paper book state at a point in time.
    
    Tracks positions, cash, and portfolio weights.
    """
    
    asof: date
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    
    def total_market_value(self, prices: Dict[str, float]) -> float:
        """Total market value of all positions."""
        return sum(
            pos.market_value(prices.get(ticker, 0))
            for ticker, pos in self.positions.items()
        )
    
    def total_value(self, prices: Dict[str, float]) -> float:
        """Total portfolio value (cash + positions)."""
        return self.cash + self.total_market_value(prices)
    
    def weights(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Current position weights."""
        total = self.total_value(prices)
        if total <= 0:
            return {}
        return {
            ticker: pos.market_value(prices.get(ticker, 0)) / total
            for ticker, pos in self.positions.items()
        }
    
    def to_dict(self, prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        prices = prices or {}
        return {
            "asof": str(self.asof),
            "cash": round(self.cash, 2),
            "positions": {
                ticker: pos.to_dict() for ticker, pos in self.positions.items()
            },
            "total_value": round(self.total_value(prices), 2),
            "weights": {
                ticker: round(weight, 4)
                for ticker, weight in self.weights(prices).items()
            },
        }


@dataclass
class Attribution:
    """
    Attribution of ticket outcomes after asof.
    
    Realized PnL computed from later bars, labeled as after-asof.
    """
    
    ticket: Ticket
    fill: TicketFill
    realized_pnl: Optional[float] = None
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    holding_period_days: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ticket": self.ticket.to_dict(),
            "fill": self.fill.to_dict(),
            "realized_pnl": round(self.realized_pnl, 2) if self.realized_pnl else None,
            "exit_date": str(self.exit_date) if self.exit_date else None,
            "exit_price": round(self.exit_price, 2) if self.exit_price else None,
            "holding_period_days": self.holding_period_days,
            "status": "realized_after_asof" if self.realized_pnl is not None else "unrealized",
        }


@dataclass
class TicketReplayResult:
    """
    Result of PM ticket walk-forward replay.
    
    Tracks fills, book evolution, and attribution.
    """
    
    tickets: List[Ticket]
    fills: List[TicketFill]
    book_snapshots: List[PaperBook]
    attributions: List[Attribution]
    starting_capital: float
    final_book: PaperBook
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        # Get final prices for final book serialization
        final_prices = {}
        if self.book_snapshots:
            # Use last snapshot's prices if available
            pass
        
        return {
            "num_tickets": len(self.tickets),
            "num_filled": sum(1 for f in self.fills if f.filled),
            "num_unfilled": sum(1 for f in self.fills if not f.filled),
            "tickets": [t.to_dict() for t in self.tickets],
            "fills": [f.to_dict() for f in self.fills],
            "book_snapshots": [b.to_dict() for b in self.book_snapshots],
            "attributions": [a.to_dict() for a in self.attributions],
            "starting_capital": round(self.starting_capital, 2),
            "final_book": self.final_book.to_dict(),
        }


def replay_pm_tickets(
    tickets: List[Ticket],
    hist_dict: Dict[str, pd.DataFrame],
    starting_capital: float = 3000.0,
    use_next_open: bool = False,
) -> TicketReplayResult:
    """
    Replay PM tickets walk-forward, tracking fills and book state.
    
    Args:
        tickets: List of PM-issued tickets (sorted by date)
        hist_dict: Dictionary mapping ticker -> OHLCV DataFrame (must cover ticket dates + attribution horizon)
        starting_capital: Starting cash (default $3000 from July paper metadata)
        use_next_open: If True, fill at next open after ticket date; if False, fill at close on ticket date
    
    Returns:
        TicketReplayResult with fills, book snapshots, and attributions
    """
    # Sort tickets by date
    tickets = sorted(tickets, key=lambda t: t.date)
    
    fills = []
    book_snapshots = []
    attributions = []
    
    # Initialize paper book
    book = PaperBook(
        asof=tickets[0].date if tickets else date.today(),
        cash=starting_capital,
    )
    
    for ticket in tickets:
        # Get price data for this ticker
        hist = hist_dict.get(ticket.ticker)
        if hist is None:
            # Cannot fill without price data
            fill = TicketFill(
                ticket=ticket,
                filled=False,
                unfilled_reason=f"No price data available for {ticket.ticker}",
            )
            fills.append(fill)
            continue
        
        if not isinstance(hist.index, pd.DatetimeIndex):
            hist.index = pd.to_datetime(hist.index)
        
        # Find fill price
        fill_price = None
        fill_date = None
        
        if use_next_open:
            # Fill at next open after ticket date
            future_bars = hist.loc[hist.index.date > ticket.date]
            if not future_bars.empty:
                fill_date = future_bars.index[0].date()
                fill_price = float(future_bars["Open"].iloc[0])
        else:
            # Fill at close on ticket date (last_print = Close <= asof)
            asof_bars = hist.loc[hist.index.date <= ticket.date]
            if not asof_bars.empty:
                fill_date = asof_bars.index[-1].date()
                fill_price = float(asof_bars["Close"].iloc[-1])
        
        if fill_price is None:
            # Cannot fill - no bar available
            fill = TicketFill(
                ticket=ticket,
                filled=False,
                unfilled_reason=f"No bar available on/after {ticket.date}",
            )
            fills.append(fill)
            continue
        
        # Check limit price if specified
        if ticket.limit is not None:
            if ticket.action in (TicketAction.BUY, TicketAction.ADD):
                if fill_price > ticket.limit:
                    fill = TicketFill(
                        ticket=ticket,
                        filled=False,
                        unfilled_reason=f"Price {fill_price} > limit {ticket.limit}",
                    )
                    fills.append(fill)
                    continue
            elif ticket.action in (TicketAction.TRIM, TicketAction.SELL):
                if fill_price < ticket.limit:
                    fill = TicketFill(
                        ticket=ticket,
                        filled=False,
                        unfilled_reason=f"Price {fill_price} < limit {ticket.limit}",
                    )
                    fills.append(fill)
                    continue
        
        # Execute ticket
        fill_qty = None
        
        if ticket.action == TicketAction.BUY:
            # Buy new position
            qty = ticket.qty if ticket.qty else (book.cash * (ticket.weight or 1.0)) / fill_price
            cost = qty * fill_price
            if cost > book.cash:
                # Insufficient cash
                fill = TicketFill(
                    ticket=ticket,
                    filled=False,
                    unfilled_reason=f"Insufficient cash: need {cost:.2f}, have {book.cash:.2f}",
                )
                fills.append(fill)
                continue
            
            book.cash -= cost
            if ticket.ticker in book.positions:
                # Average up existing position
                pos = book.positions[ticket.ticker]
                total_qty = pos.qty + qty
                total_cost = pos.cost_basis + cost
                pos.qty = total_qty
                pos.avg_cost = total_cost / total_qty
            else:
                book.positions[ticket.ticker] = Position(
                    ticker=ticket.ticker,
                    qty=qty,
                    avg_cost=fill_price,
                )
            fill_qty = qty
        
        elif ticket.action == TicketAction.ADD:
            # Add to existing position
            qty = ticket.qty if ticket.qty else (book.cash * (ticket.weight or 0.5)) / fill_price
            cost = qty * fill_price
            if cost > book.cash:
                fill = TicketFill(
                    ticket=ticket,
                    filled=False,
                    unfilled_reason=f"Insufficient cash: need {cost:.2f}, have {book.cash:.2f}",
                )
                fills.append(fill)
                continue
            
            book.cash -= cost
            if ticket.ticker in book.positions:
                pos = book.positions[ticket.ticker]
                total_qty = pos.qty + qty
                total_cost = pos.cost_basis + cost
                pos.qty = total_qty
                pos.avg_cost = total_cost / total_qty
            else:
                book.positions[ticket.ticker] = Position(
                    ticker=ticket.ticker,
                    qty=qty,
                    avg_cost=fill_price,
                )
            fill_qty = qty
        
        elif ticket.action == TicketAction.TRIM:
            # Reduce position
            if ticket.ticker not in book.positions:
                fill = TicketFill(
                    ticket=ticket,
                    filled=False,
                    unfilled_reason=f"No position in {ticket.ticker} to trim",
                )
                fills.append(fill)
                continue
            
            pos = book.positions[ticket.ticker]
            qty = ticket.qty if ticket.qty else pos.qty * (ticket.weight or 0.5)
            qty = min(qty, pos.qty)  # Cannot trim more than we have
            
            proceeds = qty * fill_price
            book.cash += proceeds
            pos.qty -= qty
            
            if pos.qty <= 0:
                del book.positions[ticket.ticker]
            
            fill_qty = qty
        
        elif ticket.action == TicketAction.SELL:
            # Close position
            if ticket.ticker not in book.positions:
                fill = TicketFill(
                    ticket=ticket,
                    filled=False,
                    unfilled_reason=f"No position in {ticket.ticker} to sell",
                )
                fills.append(fill)
                continue
            
            pos = book.positions[ticket.ticker]
            qty = ticket.qty if ticket.qty else pos.qty
            qty = min(qty, pos.qty)
            
            proceeds = qty * fill_price
            book.cash += proceeds
            pos.qty -= qty
            
            if pos.qty <= 0:
                del book.positions[ticket.ticker]
            
            fill_qty = qty
        
        elif ticket.action == TicketAction.REBALANCE:
            # Rebalance to target weight
            # Get current prices for all positions
            current_prices = {}
            for t, pos in book.positions.items():
                h = hist_dict.get(t)
                if h is not None:
                    asof_bars = h.loc[h.index.date <= ticket.date]
                    if not asof_bars.empty:
                        current_prices[t] = float(asof_bars["Close"].iloc[-1])
            
            total_value = book.total_value(current_prices)
            target_value = total_value * ticket.weight
            current_value = book.positions.get(ticket.ticker, Position(ticket.ticker, 0, 0)).market_value(fill_price)
            
            delta_value = target_value - current_value
            delta_qty = delta_value / fill_price
            
            if delta_qty > 0:
                # Buy to rebalance
                cost = delta_qty * fill_price
                if cost > book.cash:
                    fill = TicketFill(
                        ticket=ticket,
                        filled=False,
                        unfilled_reason=f"Insufficient cash for rebalance: need {cost:.2f}, have {book.cash:.2f}",
                    )
                    fills.append(fill)
                    continue
                
                book.cash -= cost
                if ticket.ticker in book.positions:
                    pos = book.positions[ticket.ticker]
                    total_qty = pos.qty + delta_qty
                    total_cost = pos.cost_basis + cost
                    pos.qty = total_qty
                    pos.avg_cost = total_cost / total_qty
                else:
                    book.positions[ticket.ticker] = Position(
                        ticker=ticket.ticker,
                        qty=delta_qty,
                        avg_cost=fill_price,
                    )
                fill_qty = delta_qty
            else:
                # Sell to rebalance
                if ticket.ticker not in book.positions:
                    fill = TicketFill(
                        ticket=ticket,
                        filled=False,
                        unfilled_reason=f"No position in {ticket.ticker} to rebalance",
                    )
                    fills.append(fill)
                    continue
                
                pos = book.positions[ticket.ticker]
                qty = abs(delta_qty)
                qty = min(qty, pos.qty)
                
                proceeds = qty * fill_price
                book.cash += proceeds
                pos.qty -= qty
                
                if pos.qty <= 0:
                    del book.positions[ticket.ticker]
                
                fill_qty = -qty
        
        # Record fill
        fill = TicketFill(
            ticket=ticket,
            filled=True,
            fill_date=fill_date,
            fill_price=fill_price,
            fill_qty=fill_qty,
        )
        fills.append(fill)
        
        # Snapshot book after this ticket
        book.asof = fill_date
        book_snapshots.append(PaperBook(
            asof=book.asof,
            cash=book.cash,
            positions={t: Position(p.ticker, p.qty, p.avg_cost) for t, p in book.positions.items()},
        ))
    
    # Compute attributions (realized PnL after asof)
    # For each filled ticket, find the exit (if any) and compute realized PnL
    # This is a simplified attribution - real implementation would track FIFO/LIFO
    
    for fill in fills:
        if not fill.filled:
            continue
        
        ticket = fill.ticket
        
        # For sell/trim tickets, compute realized PnL
        if ticket.action in (TicketAction.SELL, TicketAction.TRIM):
            # Find the original position cost basis
            # Simplified: use fill price vs current avg cost
            # Real implementation would track lots
            attribution = Attribution(
                ticket=ticket,
                fill=fill,
                realized_pnl=None,  # Stub - requires lot tracking
                exit_date=fill.fill_date,
                exit_price=fill.fill_price,
            )
            attributions.append(attribution)
    
    return TicketReplayResult(
        tickets=tickets,
        fills=fills,
        book_snapshots=book_snapshots,
        attributions=attributions,
        starting_capital=starting_capital,
        final_book=book,
    )
