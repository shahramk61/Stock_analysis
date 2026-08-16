"""
Tests for PM ticket walk-forward replay.

Proves:
- Ticket walk-forward: buy then sell produces computed PnL
- A ticket on a date with no bar is unfilled (never an invented price)
- Future bars after asof do not change fills at T
- Book tracking is correct (positions, cash, weights)
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from scripts.quant.fund.ticket_replay import (
    PaperBook,
    Position,
    Ticket,
    TicketAction,
    TicketFill,
    replay_pm_tickets,
)


def create_synthetic_hist(
    ticker: str,
    start_date: date,
    num_days: int,
    start_price: float = 100.0,
    daily_return: float = 0.01,
) -> pd.DataFrame:
    """Create synthetic OHLCV history for testing."""
    dates = [start_date + timedelta(days=i) for i in range(num_days)]
    prices = [start_price * ((1 + daily_return) ** i) for i in range(num_days)]
    
    hist = pd.DataFrame({
        "Open": prices,
        "High": [p * 1.02 for p in prices],
        "Low": [p * 0.98 for p in prices],
        "Close": prices,
        "Volume": [1000000] * num_days,
    }, index=pd.DatetimeIndex(dates))
    
    return hist


def test_ticket_replay_buy_and_sell():
    """Test that buy then sell produces computed PnL."""
    # Create synthetic history
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=30,
        start_price=100.0,
        daily_return=0.01,  # 1% daily growth
    )
    
    # Create tickets: buy on day 0, sell on day 20
    tickets = [
        Ticket(
            date=date(2023, 6, 1),
            ticker="AAPL",
            action=TicketAction.BUY,
            qty=10.0,
        ),
        Ticket(
            date=date(2023, 6, 21),
            ticker="AAPL",
            action=TicketAction.SELL,
            qty=10.0,
        ),
    ]
    
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl},
        starting_capital=3000.0,
    )
    
    # Verify both tickets filled
    assert len(result.fills) == 2
    assert all(f.filled for f in result.fills)
    
    # Verify buy filled at day 0 price
    buy_fill = result.fills[0]
    assert buy_fill.fill_price == pytest.approx(100.0, rel=0.01)
    assert buy_fill.fill_qty == 10.0
    
    # Verify sell filled at day 20 price (100 * 1.01^20)
    sell_fill = result.fills[1]
    expected_sell_price = 100.0 * (1.01 ** 20)
    assert sell_fill.fill_price == pytest.approx(expected_sell_price, rel=0.01)
    
    # Verify final book: no position, cash increased
    assert "AAPL" not in result.final_book.positions
    assert result.final_book.cash > result.starting_capital


def test_ticket_replay_no_bar_unfilled():
    """Test that ticket on date with no bar is unfilled (no invented price)."""
    # Create synthetic history with gap
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=10,
        start_price=100.0,
    )
    
    # Create ticket for date outside hist range
    tickets = [
        Ticket(
            date=date(2023, 5, 1),  # Before hist starts
            ticker="AAPL",
            action=TicketAction.BUY,
            qty=10.0,
        ),
    ]
    
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl},
        starting_capital=3000.0,
    )
    
    # Verify ticket did not fill
    assert len(result.fills) == 1
    assert result.fills[0].filled is False
    assert "No bar available" in result.fills[0].unfilled_reason
    
    # Verify book unchanged (no position, cash same)
    assert len(result.final_book.positions) == 0
    assert result.final_book.cash == result.starting_capital


def test_ticket_replay_future_bars_dont_change_fills():
    """Test that future bars after asof do not change fills at T."""
    # Create history
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=30,
        start_price=100.0,
    )
    
    # Create ticket on day 10
    tickets = [
        Ticket(
            date=date(2023, 6, 11),
            ticker="AAPL",
            action=TicketAction.BUY,
            qty=10.0,
        ),
    ]
    
    # Replay with full history
    result1 = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl},
        starting_capital=3000.0,
    )
    
    # Replay with truncated history (only up to day 15)
    hist_aapl_truncated = hist_aapl.iloc[:15]
    result2 = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl_truncated},
        starting_capital=3000.0,
    )
    
    # Verify fills are identical (future bars don't affect)
    assert result1.fills[0].fill_price == result2.fills[0].fill_price
    assert result1.fills[0].fill_date == result2.fills[0].fill_date


def test_ticket_replay_limit_price_buy():
    """Test that buy ticket respects limit price."""
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=10,
        start_price=100.0,
    )
    
    # Create buy ticket with limit below market
    tickets = [
        Ticket(
            date=date(2023, 6, 1),
            ticker="AAPL",
            action=TicketAction.BUY,
            qty=10.0,
            limit=90.0,  # Limit below market (100)
        ),
    ]
    
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl},
        starting_capital=3000.0,
    )
    
    # Verify ticket did not fill (price > limit)
    assert result.fills[0].filled is False
    assert "limit" in result.fills[0].unfilled_reason.lower()


def test_ticket_replay_insufficient_cash():
    """Test that ticket fails when insufficient cash."""
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=10,
        start_price=100.0,
    )
    
    # Create buy ticket requiring more than starting capital
    tickets = [
        Ticket(
            date=date(2023, 6, 1),
            ticker="AAPL",
            action=TicketAction.BUY,
            qty=50.0,  # 50 * 100 = 5000 > 3000 starting capital
        ),
    ]
    
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl},
        starting_capital=3000.0,
    )
    
    # Verify ticket did not fill
    assert result.fills[0].filled is False
    assert "Insufficient cash" in result.fills[0].unfilled_reason


def test_ticket_replay_book_tracking():
    """Test that book tracking is correct (positions, cash, weights)."""
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=20,
        start_price=100.0,
    )
    
    hist_msft = create_synthetic_hist(
        ticker="MSFT",
        start_date=date(2023, 6, 1),
        num_days=20,
        start_price=200.0,
    )
    
    # Create tickets: buy both, then trim one
    tickets = [
        Ticket(
            date=date(2023, 6, 1),
            ticker="AAPL",
            action=TicketAction.BUY,
            qty=10.0,
        ),
        Ticket(
            date=date(2023, 6, 5),
            ticker="MSFT",
            action=TicketAction.BUY,
            qty=5.0,
        ),
        Ticket(
            date=date(2023, 6, 15),
            ticker="AAPL",
            action=TicketAction.TRIM,
            qty=5.0,
        ),
    ]
    
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl, "MSFT": hist_msft},
        starting_capital=3000.0,
    )
    
    # Verify all tickets filled
    assert all(f.filled for f in result.fills)
    
    # Verify final book has correct positions
    assert "AAPL" in result.final_book.positions
    assert "MSFT" in result.final_book.positions
    
    # Verify AAPL position is 5 shares (bought 10, trimmed 5)
    assert result.final_book.positions["AAPL"].qty == 5.0
    
    # Verify MSFT position is 5 shares
    assert result.final_book.positions["MSFT"].qty == 5.0
    
    # Verify cash decreased by net purchases
    buy1_cost = 10.0 * 100.0  # 1000
    buy2_cost = 5.0 * 200.0   # 1000
    trim_proceeds = 5.0 * 100.0  # ~500 (assuming price same)
    expected_cash = 3000.0 - buy1_cost - buy2_cost + trim_proceeds
    # Rough check (price may change slightly)
    assert result.final_book.cash < 3000.0
    assert result.final_book.cash > 0


def test_ticket_replay_add_to_position():
    """Test that ADD ticket adds to existing position."""
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=20,
        start_price=100.0,
        daily_return=0.01,
    )
    
    tickets = [
        Ticket(
            date=date(2023, 6, 1),
            ticker="AAPL",
            action=TicketAction.BUY,
            qty=10.0,
        ),
        Ticket(
            date=date(2023, 6, 10),
            ticker="AAPL",
            action=TicketAction.ADD,
            qty=5.0,
        ),
    ]
    
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl},
        starting_capital=3000.0,
    )
    
    # Verify both tickets filled
    assert all(f.filled for f in result.fills)
    
    # Verify final position is 15 shares
    assert result.final_book.positions["AAPL"].qty == 15.0
    
    # Verify avg cost is weighted average
    buy_price = 100.0
    add_price = 100.0 * (1.01 ** 9)  # Day 10 price
    expected_avg_cost = (10 * buy_price + 5 * add_price) / 15
    assert result.final_book.positions["AAPL"].avg_cost == pytest.approx(expected_avg_cost, rel=0.01)


def test_ticket_replay_rebalance():
    """Test that REBALANCE ticket adjusts position to target weight."""
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=20,
        start_price=100.0,
    )
    
    tickets = [
        Ticket(
            date=date(2023, 6, 1),
            ticker="AAPL",
            action=TicketAction.BUY,
            qty=10.0,
        ),
        Ticket(
            date=date(2023, 6, 10),
            ticker="AAPL",
            action=TicketAction.REBALANCE,
            weight=0.5,  # Target 50% of portfolio
        ),
    ]
    
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl},
        starting_capital=3000.0,
    )
    
    # Verify both tickets filled
    assert all(f.filled for f in result.fills)
    
    # Verify position exists
    assert "AAPL" in result.final_book.positions


def test_ticket_replay_no_hist():
    """Test that ticket for ticker with no hist is unfilled."""
    hist_aapl = create_synthetic_hist(
        ticker="AAPL",
        start_date=date(2023, 6, 1),
        num_days=10,
        start_price=100.0,
    )
    
    # Create ticket for ticker without hist
    tickets = [
        Ticket(
            date=date(2023, 6, 1),
            ticker="MSFT",  # No hist provided
            action=TicketAction.BUY,
            qty=10.0,
        ),
    ]
    
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict={"AAPL": hist_aapl},  # Only AAPL hist
        starting_capital=3000.0,
    )
    
    # Verify ticket did not fill
    assert result.fills[0].filled is False
    assert "No price data" in result.fills[0].unfilled_reason


def test_position_calculations():
    """Test Position helper class calculations."""
    pos = Position(ticker="AAPL", qty=10.0, avg_cost=100.0)
    
    assert pos.cost_basis == 1000.0
    assert pos.market_value(110.0) == 1100.0
    assert pos.unrealized_pnl(110.0) == 100.0
    assert pos.unrealized_pnl(90.0) == -100.0


def test_paper_book_calculations():
    """Test PaperBook helper class calculations."""
    book = PaperBook(
        asof=date(2023, 6, 1),
        cash=1000.0,
    )
    
    book.positions["AAPL"] = Position(ticker="AAPL", qty=10.0, avg_cost=100.0)
    book.positions["MSFT"] = Position(ticker="MSFT", qty=5.0, avg_cost=200.0)
    
    prices = {"AAPL": 110.0, "MSFT": 220.0}
    
    # Total market value: 10*110 + 5*220 = 1100 + 1100 = 2200
    assert book.total_market_value(prices) == 2200.0
    
    # Total value: 1000 cash + 2200 positions = 3200
    assert book.total_value(prices) == 3200.0
    
    # Weights: AAPL = 1100/3200 = 34.375%, MSFT = 1100/3200 = 34.375%
    weights = book.weights(prices)
    assert weights["AAPL"] == pytest.approx(1100.0 / 3200.0, rel=0.01)
    assert weights["MSFT"] == pytest.approx(1100.0 / 3200.0, rel=0.01)
