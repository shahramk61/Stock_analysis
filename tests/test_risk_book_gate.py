"""
Tests for fund-level book constraint risk gate.

Tests cover:
- Missing NAV → BLOCK
- Missing asof mark → BLOCK
- ADD over name/cash/theme limits → BLOCK
- CIO hold + death cross / high VaR → ALLOW (not blocked)
- TRIM that strands cash/names → FLAG
- Theme purity, liquidity, sector concentration
- First-add correlation exception
- Factor cluster checks for multi-name ADD
"""

import os
import sys
import unittest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from risk.book_gate import (  # noqa: E402
    Book,
    Position,
    RiskDecision,
    check_book_constraints,
)
from risk import limits  # noqa: E402


class TestBookConstraintGate(unittest.TestCase):
    """Test suite for book constraint validation."""
    
    def test_missing_nav_blocks(self):
        """Missing NAV should BLOCK with fail-closed."""
        book = Book(nav=None, cash=100000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=5.0,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertIn("NAV", decision.missing)
        self.assertIn("NAV", decision.reason)
    
    def test_missing_asof_blocks(self):
        """Missing asof date should BLOCK with fail-closed."""
        book = Book(nav=1000000, cash=100000, asof=None)
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=5.0,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertIn("asof", decision.missing)
        self.assertIn("asof", decision.reason)
    
    def test_cio_hold_with_death_cross_allows(self):
        """CIO-approved HOLD should ALLOW even with death cross/high VaR.
        
        The book constraint model does NOT veto holds based on VaR, CVaR,
        death cross, or Bear regime. Those are research signals, not fund-level risk.
        """
        book = Book(nav=1000000, cash=100000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="GME",
            ticket_type="HOLD",
            book=book,
            cio_approved=True,
        )
        
        self.assertEqual(decision.decision, "ALLOW")
        self.assertTrue(decision.cio_approved)
        self.assertIn("CIO-approved", decision.reason)
    
    def test_regular_hold_allows(self):
        """Regular HOLD (non-CIO) should also ALLOW under book constraint model."""
        book = Book(nav=1000000, cash=100000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="TSLA",
            ticket_type="HOLD",
            book=book,
            cio_approved=False,
        )
        
        self.assertEqual(decision.decision, "ALLOW")
        self.assertFalse(decision.cio_approved)
    
    def test_buy_exceeds_single_name_limit_blocks(self):
        """BUY that exceeds single name 10% limit should BLOCK."""
        book = Book(nav=1000000, cash=500000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=15.0,  # Exceeds 10% limit
            theme="AI",
            liquidity_adv=50000000,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("single name limit" in r for r in decision.reasons))
    
    def test_buy_exceeds_cash_limit_blocks(self):
        """BUY that would drop cash below 10% should BLOCK."""
        book = Book(nav=1000000, cash=150000, asof="2026-08-16")  # 15% cash
        
        decision = check_book_constraints(
            ticker="MSFT",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,  # Would use 80k, leaving 70k (7%)
            theme="Cloud",
            liquidity_adv=100000000,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("cash" in r.lower() for r in decision.reasons))
    
    def test_buy_exceeds_sector_theme_limit_blocks(self):
        """BUY that exceeds 25% sector/theme limit should BLOCK."""
        # Book with 20% in "AI" theme already
        positions = [
            Position("NVDA", weight_pct=10.0, theme="AI", liquidity_adv=200000000),
            Position("AMD", weight_pct=10.0, theme="AI", liquidity_adv=150000000),
        ]
        book = Book(nav=1000000, cash=700000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="GOOGL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,  # Would make AI theme 28%
            theme="AI",
            liquidity_adv=300000000,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("theme" in r.lower() or "sector" in r.lower() for r in decision.reasons))
    
    def test_buy_exceeds_max_names_blocks(self):
        """BUY that exceeds 20 names limit should BLOCK."""
        # Create book with 20 positions already
        positions = [
            Position(f"TICK{i}", weight_pct=4.0, theme="Tech", liquidity_adv=50000000)
            for i in range(20)
        ]
        book = Book(nav=1000000, cash=200000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="NEWCO",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=3.0,
            theme="Tech",
            liquidity_adv=40000000,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("name count" in r.lower() for r in decision.reasons))
    
    def test_buy_missing_theme_blocks(self):
        """BUY without theme tag should BLOCK (theme purity)."""
        book = Book(nav=1000000, cash=500000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=5.0,
            theme=None,  # Missing theme
            liquidity_adv=500000000,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertIn("theme", decision.missing)
    
    def test_buy_missing_liquidity_blocks(self):
        """BUY without liquidity ADV should BLOCK (fail-closed)."""
        book = Book(nav=1000000, cash=500000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=5.0,
            theme="Tech",
            liquidity_adv=None,  # Missing liquidity
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertIn("liquidity_adv", decision.missing)
    
    def test_add_missing_liquidity_blocks(self):
        """ADD to existing position without liquidity ADV should BLOCK."""
        positions = [Position("AAPL", weight_pct=5.0, theme="Tech", liquidity_adv=500000000)]
        book = Book(nav=1000000, cash=400000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="ADD",
            book=book,
            proposed_weight_pct=8.0,  # Adding to existing 5%
            theme="Tech",
            liquidity_adv=None,  # Missing for ADD
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertIn("liquidity_adv", decision.missing)
    
    def test_first_add_no_correlation_required(self):
        """First BUY doesn't require correlation data (exception)."""
        book = Book(nav=1000000, cash=500000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,
            theme="Tech",
            liquidity_adv=500000000,
            correlation_data=None,  # No correlation for first add
        )
        
        self.assertEqual(decision.decision, "ALLOW")
        self.assertNotIn("correlation_data", decision.missing)
    
    def test_multi_name_add_missing_correlation_blocks(self):
        """Multi-name ADD without correlation data should BLOCK."""
        positions = [Position("NVDA", weight_pct=8.0, theme="AI", liquidity_adv=200000000)]
        book = Book(nav=1000000, cash=400000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AMD",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,
            theme="Semiconductors",
            liquidity_adv=150000000,
            correlation_data=None,  # Missing for multi-name
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertIn("correlation_data", decision.missing)
    
    def test_factor_cluster_exceeds_limit_blocks(self):
        """ADD that exceeds 35% factor cluster limit should BLOCK."""
        positions = [
            Position("NVDA", weight_pct=15.0, theme="AI", liquidity_adv=200000000),
            Position("AMD", weight_pct=12.0, theme="Semiconductors", liquidity_adv=150000000),
        ]
        book = Book(nav=1000000, cash=400000, positions=positions, asof="2026-08-16")
        
        # High correlation between AMD, NVDA, and new position
        correlation_data = {
            "NVDA": 0.8,  # High correlation
            "AMD": 0.7,   # High correlation
        }
        
        decision = check_book_constraints(
            ticker="INTC",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=10.0,  # Would make cluster 15 + 12 + 10 = 37%
            theme="Semiconductors",
            liquidity_adv=180000000,
            correlation_data=correlation_data,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("factor cluster" in r.lower() for r in decision.reasons))
    
    def test_trim_strands_names_flags(self):
        """SELL that leaves too few names should FLAG (not block)."""
        positions = [
            Position("AAPL", weight_pct=30.0, theme="Tech", liquidity_adv=500000000),
            Position("MSFT", weight_pct=30.0, theme="Tech", liquidity_adv=400000000),
            Position("GOOGL", weight_pct=30.0, theme="Tech", liquidity_adv=300000000),
        ]
        book = Book(nav=1000000, cash=100000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="GOOGL",
            ticket_type="SELL",
            book=book,
        )
        
        # Should FLAG because post-trade would have 2 names (below min of 3)
        self.assertEqual(decision.decision, "FLAG")
        self.assertTrue(any("name count" in r.lower() for r in decision.reasons))
    
    def test_sell_orphans_theme_flags(self):
        """SELL that orphans a theme should FLAG."""
        positions = [
            Position("AAPL", weight_pct=30.0, theme="Tech", liquidity_adv=500000000),
            Position("XOM", weight_pct=20.0, theme="Energy", liquidity_adv=200000000),  # Only Energy
            Position("JPM", weight_pct=20.0, theme="Finance", liquidity_adv=250000000),
            Position("UNH", weight_pct=20.0, theme="Healthcare", liquidity_adv=180000000),
        ]
        book = Book(nav=1000000, cash=100000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="XOM",
            ticket_type="SELL",
            book=book,
        )
        
        # Should FLAG because Energy theme would be orphaned
        self.assertEqual(decision.decision, "FLAG")
        self.assertTrue(any("orphan" in r.lower() for r in decision.reasons))
    
    def test_valid_buy_allows(self):
        """Valid BUY within all constraints should ALLOW."""
        positions = [
            Position("AAPL", weight_pct=8.0, theme="Tech", liquidity_adv=500000000),
            Position("MSFT", weight_pct=7.0, theme="Tech", liquidity_adv=400000000),
        ]
        book = Book(nav=1000000, cash=500000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="GOOGL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,
            theme="Tech",
            liquidity_adv=300000000,
            correlation_data={"AAPL": 0.3, "MSFT": 0.4},  # Low correlation
        )
        
        self.assertEqual(decision.decision, "ALLOW")
        self.assertEqual(len(decision.reasons), 1)
        self.assertIn("passes", decision.reasons[0].lower())
    
    def test_valid_trim_allows(self):
        """Valid TRIM that doesn't strand the book should ALLOW."""
        positions = [
            Position("AAPL", weight_pct=12.0, theme="Tech", liquidity_adv=500000000),
            Position("MSFT", weight_pct=10.0, theme="Tech", liquidity_adv=400000000),
            Position("GOOGL", weight_pct=10.0, theme="Tech", liquidity_adv=300000000),
            Position("AMZN", weight_pct=10.0, theme="Ecommerce", liquidity_adv=350000000),
            Position("TSLA", weight_pct=8.0, theme="Auto", liquidity_adv=200000000),
        ]
        book = Book(nav=1000000, cash=500000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="TRIM",
            book=book,
            proposed_weight_pct=8.0,  # Trim from 12% to 8%
        )
        
        self.assertEqual(decision.decision, "ALLOW")
    
    def test_to_veto_object_format(self):
        """Test conversion to legacy veto object format."""
        book = Book(nav=1000000, cash=100000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=15.0,
            theme="Tech",
            liquidity_adv=500000000,
        )
        
        veto_obj = decision.to_veto_object()
        
        self.assertIn("action", veto_obj)
        self.assertEqual(veto_obj["action"], "BLOCK")
        self.assertEqual(veto_obj["ticker"], "AAPL")
        self.assertEqual(veto_obj["ticket_type"], "BUY")
        self.assertIn("details", veto_obj)
        self.assertIn("reasons", veto_obj["details"])
    
    def test_to_dict_format(self):
        """Test conversion to dictionary format."""
        book = Book(nav=1000000, cash=500000, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="HOLD",
            book=book,
            cio_approved=True,
        )
        
        d = decision.to_dict()
        
        self.assertEqual(d["decision"], "ALLOW")
        self.assertEqual(d["ticker"], "AAPL")
        self.assertEqual(d["ticket"], "HOLD")
        self.assertEqual(d["asof"], "2026-08-16")
        self.assertTrue(d["cio_approved"])
        self.assertIn("reason", d)
        self.assertIn("reasons", d)
        self.assertIn("missing", d)
    
    def test_liquidity_constraint_enforced(self):
        """Test that position size vs ADV is enforced."""
        book = Book(nav=1000000, cash=500000, asof="2026-08-16")
        
        # Position of $80k with ADV of $1M means we need ADV/20 = $50k max
        decision = check_book_constraints(
            ticker="SMALLCAP",
            ticket_type="BUY",
            book=book,
            proposed_notional=80000,  # Exceeds 1M/20 = 50k
            theme="SmallCap",
            liquidity_adv=1000000,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("liquidity" in r.lower() for r in decision.reasons))


class TestBookHelpers(unittest.TestCase):
    """Test Book and Position helper methods."""
    
    def test_book_cash_pct(self):
        """Test cash percentage calculation."""
        book = Book(nav=1000000, cash=150000)
        self.assertEqual(book.cash_pct, 15.0)
    
    def test_book_cash_pct_missing_nav(self):
        """Test cash percentage with missing NAV."""
        book = Book(nav=None, cash=150000)
        self.assertIsNone(book.cash_pct)
    
    def test_book_num_names(self):
        """Test name count."""
        positions = [
            Position("AAPL", weight_pct=10.0),
            Position("MSFT", weight_pct=10.0),
        ]
        book = Book(positions=positions)
        self.assertEqual(book.num_names, 2)
    
    def test_book_get_position(self):
        """Test finding a position by ticker."""
        positions = [
            Position("AAPL", weight_pct=10.0),
            Position("MSFT", weight_pct=8.0),
        ]
        book = Book(positions=positions)
        
        pos = book.get_position("AAPL")
        self.assertIsNotNone(pos)
        self.assertEqual(pos.ticker, "AAPL")
        self.assertEqual(pos.weight_pct, 10.0)
        
        pos2 = book.get_position("GOOGL")
        self.assertIsNone(pos2)
    
    def test_book_sector_theme_exposure(self):
        """Test sector/theme exposure calculation."""
        positions = [
            Position("AAPL", weight_pct=10.0, theme="Tech"),
            Position("MSFT", weight_pct=8.0, theme="Tech"),
            Position("GOOGL", weight_pct=7.0, theme="Tech"),
            Position("XOM", weight_pct=5.0, theme="Energy"),
        ]
        book = Book(positions=positions)
        
        tech_exposure = book.sector_theme_exposure("Tech")
        self.assertEqual(tech_exposure, 25.0)
        
        energy_exposure = book.sector_theme_exposure("Energy")
        self.assertEqual(energy_exposure, 5.0)
        
        missing_exposure = book.sector_theme_exposure("Finance")
        self.assertEqual(missing_exposure, 0.0)


if __name__ == "__main__":
    unittest.main()
