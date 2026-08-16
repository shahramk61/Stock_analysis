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
    
    def test_fractional_shares_allow(self):
        """
        Fractional shares: Check dollar weight vs 10% name cap, not share count.
        
        NAV $3000, TSLA at $342/share, ticket $300 (fractional 0.877 shares).
        $300 is 10% of $3000 NAV → should ALLOW on name cap (not block because 1 share > 10%).
        """
        book = Book(nav=3000, cash=1500, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="TSLA",
            ticket_type="BUY",
            book=book,
            proposed_notional=300,  # $300 ticket (fractional shares)
            theme="EV",
            liquidity_adv=100000000,  # Adequate liquidity
        )
        
        # Should ALLOW because $300 / $3000 = 10.0% exactly (at name cap limit)
        self.assertEqual(decision.decision, "ALLOW")
    
    def test_fractional_shares_small_nav_allow(self):
        """
        Even smaller fractional case: NAV $1000, TSLA $342, ticket $100.
        $100 / $1000 = 10% → ALLOW.
        """
        book = Book(nav=1000, cash=500, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="TSLA",
            ticket_type="BUY",
            book=book,
            proposed_notional=100,  # 10% of NAV
            theme="EV",
            liquidity_adv=100000000,
        )
        
        self.assertEqual(decision.decision, "ALLOW")
    
    def test_fractional_shares_exceeds_blocks(self):
        """
        Fractional shares that exceed 10% should still BLOCK.
        NAV $3000, ticket $350 → 11.67% → BLOCK.
        """
        book = Book(nav=3000, cash=1500, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="TSLA",
            ticket_type="BUY",
            book=book,
            proposed_notional=350,  # Exceeds 10% of NAV
            theme="EV",
            liquidity_adv=100000000,
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("single name limit" in r for r in decision.reasons))
    
    def test_option_sleeve_cap_enforced(self):
        """
        Option sleeve cap: max 20% NAV for names marked as missing 15% hurdle.
        
        Book has 15% in marked option sleeve names.
        Adding 8% more marked name → 23% total → BLOCK.
        """
        positions = [
            Position(
                "SPEC1", weight_pct=8.0, theme="Speculative",
                liquidity_adv=50000000, option_sleeve=True  # Marked
            ),
            Position(
                "SPEC2", weight_pct=7.0, theme="Speculative",
                liquidity_adv=40000000, hurdle_15pct="miss"  # Marked
            ),
            Position(
                "CORE", weight_pct=10.0, theme="Core",
                liquidity_adv=500000000  # Not marked (no option sleeve)
            ),
        ]
        book = Book(nav=1000000, cash=500000, positions=positions, asof="2026-08-16")
        
        # Current option sleeve: 8% + 7% = 15%
        self.assertEqual(book.option_sleeve_exposure(), 15.0)
        
        # Try to add 8% more marked name → would be 23%
        decision = check_book_constraints(
            ticker="SPEC3",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,
            theme="Speculative",
            liquidity_adv=30000000,
            option_sleeve=True,  # Marked for option sleeve
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("option sleeve" in r.lower() for r in decision.reasons))
    
    def test_option_sleeve_unmarked_not_counted(self):
        """
        Unmarked names (no option_sleeve or hurdle_15pct mark) should NOT count toward sleeve.
        Do not invent or guess marks.
        """
        positions = [
            Position(
                "SPEC1", weight_pct=8.0, theme="Speculative",
                liquidity_adv=50000000, option_sleeve=True  # Marked
            ),
            Position(
                "CORE1", weight_pct=10.0, theme="Core",
                liquidity_adv=500000000  # Not marked
            ),
            Position(
                "CORE2", weight_pct=9.0, theme="Core",
                liquidity_adv=400000000  # Not marked
            ),
        ]
        book = Book(nav=1000000, cash=500000, positions=positions, asof="2026-08-16")
        
        # Only SPEC1 is marked → 8% in sleeve
        self.assertEqual(book.option_sleeve_exposure(), 8.0)
        
        # Add 10% more marked name → 8% + 10% = 18% (under 20% limit) → ALLOW
        decision = check_book_constraints(
            ticker="SPEC2",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=10.0,  # Under single name 10% limit
            theme="Speculative",
            liquidity_adv=40000000,
            hurdle_15pct="miss",  # Marked via hurdle flag
            correlation_data={"SPEC1": 0.2, "CORE1": 0.1, "CORE2": 0.1},
        )
        
        self.assertEqual(decision.decision, "ALLOW")
    
    def test_option_sleeve_exactly_at_cap_allows(self):
        """Adding to option sleeve exactly at 20% cap should ALLOW."""
        positions = [
            Position(
                "SPEC1", weight_pct=10.0, theme="Speculative",
                liquidity_adv=50000000, option_sleeve=True
            ),
        ]
        book = Book(nav=1000000, cash=500000, positions=positions, asof="2026-08-16")
        
        # Add 10% more → exactly 20% → ALLOW
        decision = check_book_constraints(
            ticker="SPEC2",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=10.0,
            theme="Speculative",
            liquidity_adv=40000000,
            option_sleeve=True,
            correlation_data={"SPEC1": 0.3},
        )
        
        self.assertEqual(decision.decision, "ALLOW")
    
    def test_option_sleeve_one_over_cap_blocks(self):
        """Adding to option sleeve 0.1% over 20% cap should BLOCK."""
        positions = [
            Position(
                "SPEC1", weight_pct=10.0, theme="Speculative",
                liquidity_adv=50000000, option_sleeve=True
            ),
        ]
        book = Book(nav=1000000, cash=500000, positions=positions, asof="2026-08-16")
        
        # Add 10.1% more → 20.1% → BLOCK
        decision = check_book_constraints(
            ticker="SPEC2",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=10.1,
            theme="Speculative",
            liquidity_adv=40000000,
            option_sleeve=True,
            correlation_data={"SPEC1": 0.3},
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("option sleeve" in r.lower() for r in decision.reasons))


class TestBookCompletenessFlag(unittest.TestCase):
    """Test suite for book completeness FLAG (under-invested warning)."""
    
    def test_empty_ish_book_flags(self):
        """
        Empty-ish book: 2 names, 80% cash, no CIO sizing → ALLOW + completeness FLAG.
        
        Rule: FLAG when n_names < 5 AND cash_pct > 50%.
        Never BLOCK - tickets still ALLOW if other constraints pass.
        """
        positions = [
            Position("AAPL", weight_pct=10.0, theme="Tech", liquidity_adv=500000000),
            Position("XOM", weight_pct=10.0, theme="Energy", liquidity_adv=200000000),
        ]
        book = Book(nav=1000000, cash=800000, positions=positions, asof="2026-08-16")
        
        # 2 names < 5, 80% cash > 50% → should FLAG
        self.assertEqual(book.num_names, 2)
        self.assertEqual(book.cash_pct, 80.0)
        
        # Try to BUY - should ALLOW (constraints pass) but FLAG for completeness
        decision = check_book_constraints(
            ticker="GOOGL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,
            theme="Cloud",  # Different theme to avoid sector/theme limit
            liquidity_adv=300000000,
            correlation_data={"AAPL": 0.3, "XOM": 0.1},
            cio_sized=False,  # No CIO sizing
        )
        
        # Should FLAG (not BLOCK) with completeness warning
        self.assertEqual(decision.decision, "FLAG")
        self.assertTrue(any("completeness" in r.lower() for r in decision.reasons))
        self.assertTrue(any("under-invested" in r.lower() for r in decision.reasons))
        
        # Verify it's a FLAG, not a BLOCK
        self.assertNotEqual(decision.decision, "BLOCK")
    
    def test_empty_ish_book_cio_sized_no_flag(self):
        """
        Same empty-ish book (2 names, 80% cash) but CIO sized → no completeness FLAG.
        
        The FLAG dies when CIO has sized the book.
        """
        positions = [
            Position("AAPL", weight_pct=10.0, theme="Tech", liquidity_adv=500000000),
            Position("XOM", weight_pct=10.0, theme="Energy", liquidity_adv=200000000),
        ]
        book = Book(nav=1000000, cash=800000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="GOOGL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,
            theme="Cloud",
            liquidity_adv=300000000,
            correlation_data={"AAPL": 0.3, "XOM": 0.1},
            cio_sized=True,  # CIO has sized the book
        )
        
        # Should ALLOW without completeness flag
        self.assertEqual(decision.decision, "ALLOW")
        self.assertFalse(any("completeness" in r.lower() for r in decision.reasons))
    
    def test_empty_ish_book_cash_memo_no_flag(self):
        """
        Same empty-ish book but cash memo written → no completeness FLAG.
        
        The FLAG dies when CIO has written a cash memo.
        """
        positions = [
            Position("AAPL", weight_pct=10.0, theme="Tech", liquidity_adv=500000000),
            Position("XOM", weight_pct=10.0, theme="Energy", liquidity_adv=200000000),
        ]
        book = Book(nav=1000000, cash=800000, positions=positions, asof="2026-08-16")
        
        decision = check_book_constraints(
            ticker="GOOGL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,
            theme="Cloud",
            liquidity_adv=300000000,
            correlation_data={"AAPL": 0.3, "XOM": 0.1},
            cash_memo=True,  # CIO has written cash memo
        )
        
        # Should ALLOW without completeness flag
        self.assertEqual(decision.decision, "ALLOW")
        self.assertFalse(any("completeness" in r.lower() for r in decision.reasons))
    
    def test_enough_names_no_flag(self):
        """
        5 names, 70% cash → no completeness FLAG (n_names < 5 is false).
        
        Need BOTH conditions (< 5 names AND > 50% cash) to flag.
        """
        positions = [
            Position("TICK1", weight_pct=6.0, theme="Tech", liquidity_adv=100000000),
            Position("TICK2", weight_pct=6.0, theme="Energy", liquidity_adv=100000000),
            Position("TICK3", weight_pct=6.0, theme="Finance", liquidity_adv=100000000),
            Position("TICK4", weight_pct=6.0, theme="Healthcare", liquidity_adv=100000000),
            Position("TICK5", weight_pct=6.0, theme="Consumer", liquidity_adv=100000000),
        ]
        book = Book(nav=1000000, cash=700000, positions=positions, asof="2026-08-16")
        
        # 5 names (not < 5), 70% cash (> 50%) → no flag
        self.assertEqual(book.num_names, 5)
        self.assertEqual(book.cash_pct, 70.0)
        
        decision = check_book_constraints(
            ticker="NEWTICK",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=5.0,
            theme="Industrial",  # Different theme
            liquidity_adv=80000000,
            correlation_data={f"TICK{i}": 0.2 for i in range(1, 6)},
            cio_sized=False,
        )
        
        # Should ALLOW without completeness flag
        self.assertEqual(decision.decision, "ALLOW")
        self.assertFalse(any("completeness" in r.lower() for r in decision.reasons))
    
    def test_low_cash_no_flag(self):
        """
        2 names, 40% cash → no completeness FLAG (cash_pct > 50% is false).
        
        Need BOTH conditions to flag.
        """
        positions = [
            Position("AAPL", weight_pct=30.0, theme="Tech", liquidity_adv=500000000),
            Position("XOM", weight_pct=30.0, theme="Energy", liquidity_adv=200000000),
        ]
        book = Book(nav=1000000, cash=400000, positions=positions, asof="2026-08-16")
        
        # 2 names (< 5), 40% cash (not > 50%) → no flag
        self.assertEqual(book.num_names, 2)
        self.assertEqual(book.cash_pct, 40.0)
        
        decision = check_book_constraints(
            ticker="GOOGL",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=8.0,
            theme="Cloud",  # Different theme
            liquidity_adv=300000000,
            correlation_data={"AAPL": 0.3, "XOM": 0.1},
            cio_sized=False,
        )
        
        # Should ALLOW without completeness flag
        self.assertEqual(decision.decision, "ALLOW")
        self.assertFalse(any("completeness" in r.lower() for r in decision.reasons))
    
    def test_completeness_never_blocks(self):
        """
        Book completeness must never be a BLOCK, even with extreme thresholds.
        
        0 names, 100% cash → still ALLOW (FLAG at most).
        """
        book = Book(nav=1000000, cash=1000000, positions=[], asof="2026-08-16")
        
        # 0 names, 100% cash → should FLAG but never BLOCK
        decision = check_book_constraints(
            ticker="FIRST",
            ticket_type="BUY",
            book=book,
            proposed_weight_pct=5.0,
            theme="Tech",
            liquidity_adv=100000000,
            cio_sized=False,
        )
        
        # Must NOT be a BLOCK
        self.assertNotEqual(decision.decision, "BLOCK")
        
        # Should be FLAG with completeness warning
        self.assertEqual(decision.decision, "FLAG")
        self.assertTrue(any("completeness" in r.lower() for r in decision.reasons))
    
    def test_completeness_flag_on_hold(self):
        """Book completeness FLAG applies to HOLD tickets too."""
        positions = [
            Position("AAPL", weight_pct=10.0, theme="Tech", liquidity_adv=500000000),
        ]
        book = Book(nav=1000000, cash=900000, positions=positions, asof="2026-08-16")
        
        # 1 name < 5, 90% cash > 50% → should FLAG
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="HOLD",
            book=book,
            cio_sized=False,
        )
        
        # Should FLAG for completeness
        self.assertEqual(decision.decision, "FLAG")
        self.assertTrue(any("completeness" in r.lower() for r in decision.reasons))
    
    def test_completeness_flag_on_trim(self):
        """Book completeness FLAG applies to TRIM tickets too."""
        positions = [
            Position("AAPL", weight_pct=15.0, theme="Tech", liquidity_adv=500000000),
            Position("MSFT", weight_pct=10.0, theme="Tech", liquidity_adv=400000000),
        ]
        book = Book(nav=1000000, cash=750000, positions=positions, asof="2026-08-16")
        
        # 2 names < 5, 75% cash > 50% → should FLAG
        decision = check_book_constraints(
            ticker="AAPL",
            ticket_type="TRIM",
            book=book,
            proposed_weight_pct=10.0,  # Trim from 15% to 10%
            cio_sized=False,
        )
        
        # Should FLAG for completeness
        self.assertEqual(decision.decision, "FLAG")
        self.assertTrue(any("completeness" in r.lower() for r in decision.reasons))


class TestSleeveCoreBalance(unittest.TestCase):
    """Test suite for sleeve-core balance rule (desk-locked 2026-08-16)."""
    
    def test_sleeve_add_exceeds_core_blocks(self):
        """
        Sleeve ADD that would make sleeve $ > core $ should BLOCK.
        
        Rule: sleeve dollars may not exceed core dollars.
        """
        # NAV $1000, core $400, sleeve $300
        positions = [
            Position("CORE1", weight_pct=20.0, notional=200, theme="Tech", 
                    liquidity_adv=500000000),  # Core
            Position("CORE2", weight_pct=20.0, notional=200, theme="Energy", 
                    liquidity_adv=200000000),  # Core
            Position("SLEEVE1", weight_pct=30.0, notional=300, theme="Speculative",
                    liquidity_adv=50000000, option_sleeve=True),  # Sleeve
        ]
        book = Book(nav=1000, cash=300, positions=positions, asof="2026-08-16")
        
        # Verify current balance: sleeve $300, core $400 → OK
        self.assertEqual(book.sleeve_notional(), 300)
        self.assertEqual(book.core_notional(), 400)
        
        # Try to add $150 to sleeve → would be $450 sleeve > $400 core → BLOCK
        decision = check_book_constraints(
            ticker="SLEEVE2",
            ticket_type="BUY",
            book=book,
            proposed_notional=150,
            theme="Speculative",
            liquidity_adv=40000000,
            option_sleeve=True,  # Marked for sleeve
            correlation_data={"CORE1": 0.2, "CORE2": 0.1, "SLEEVE1": 0.3},
        )
        
        self.assertEqual(decision.decision, "BLOCK")
        self.assertTrue(any("sleeve" in r.lower() and "core" in r.lower() for r in decision.reasons))
    
    def test_existing_breach_hold_flags_not_flatten(self):
        """
        Existing breach: sleeve > core already.
        HOLD should FLAG but not flatten (ALLOW with warning).
        Further sleeve ADD should BLOCK.
        
        Live example: NAV $3000, SYM core $298.90, TSLA sleeve $300, WRD sleeve $300
        → sleeve $600 > core $298.90 → FLAG, no flatten, BLOCK another sleeve ADD
        """
        # Live example from user
        positions = [
            Position("SYM", weight_pct=9.96, notional=298.90, theme="Core",
                    liquidity_adv=100000000),  # Core
            Position("TSLA", weight_pct=10.0, notional=300, theme="EV",
                    liquidity_adv=150000000, option_sleeve=True),  # Sleeve
            Position("WRD", weight_pct=10.0, notional=300, theme="Speculative",
                    liquidity_adv=80000000, option_sleeve=True),  # Sleeve
        ]
        book = Book(nav=3000, cash=2101.10, positions=positions, asof="2026-08-16")
        
        # Verify breach: sleeve $600 > core $298.90
        self.assertAlmostEqual(book.sleeve_notional(), 600, places=2)
        self.assertAlmostEqual(book.core_notional(), 298.90, places=2)
        self.assertGreater(book.sleeve_notional(), book.core_notional())
        
        # HOLD on existing position → FLAG (not flatten, not BLOCK)
        decision_hold = check_book_constraints(
            ticker="TSLA",
            ticket_type="HOLD",
            book=book,
        )
        
        # Should FLAG for breach but ALLOW the hold (not flatten)
        self.assertEqual(decision_hold.decision, "FLAG")
        self.assertTrue(any("sleeve" in r.lower() and "core" in r.lower() 
                           and "breach" in r.lower() for r in decision_hold.reasons))
        self.assertNotEqual(decision_hold.decision, "BLOCK")
        
        # Further sleeve ADD should BLOCK (can't add more to sleeve until balanced)
        decision_add = check_book_constraints(
            ticker="NEWSLV",
            ticket_type="BUY",
            book=book,
            proposed_notional=100,
            theme="Speculative",
            liquidity_adv=50000000,
            option_sleeve=True,
            correlation_data={"SYM": 0.1, "TSLA": 0.3, "WRD": 0.3},
        )
        
        self.assertEqual(decision_add.decision, "BLOCK")
        self.assertTrue(any("sleeve" in r.lower() and "core" in r.lower() 
                           for r in decision_add.reasons))
    
    def test_add_core_restores_balance_allows(self):
        """
        Adding core that restores sleeve ≤ core should ALLOW (other constraints equal).
        
        Breach state: sleeve $600 > core $298.90
        Add $300 core (10% NAV) → core becomes $598.90, nearly equal to sleeve $600 → restores balance
        """
        positions = [
            Position("SYM", weight_pct=9.96, notional=298.90, theme="Core",
                    liquidity_adv=100000000),  # Core
            Position("TSLA", weight_pct=10.0, notional=300, theme="EV",
                    liquidity_adv=150000000, option_sleeve=True),  # Sleeve
            Position("WRD", weight_pct=10.0, notional=300, theme="Speculative",
                    liquidity_adv=80000000, option_sleeve=True),  # Sleeve
        ]
        book = Book(nav=3000, cash=2101.10, positions=positions, asof="2026-08-16")
        
        # Currently in breach: sleeve $600 > core $298.90
        self.assertGreater(book.sleeve_notional(), book.core_notional())
        
        # Add $300 core (10% NAV, at single name limit) → post-trade core $598.90 ≈ sleeve $600
        decision = check_book_constraints(
            ticker="NEWCORE",
            ticket_type="BUY",
            book=book,
            proposed_notional=300,  # 10% NAV
            theme="Industrial",  # Different theme
            liquidity_adv=120000000,
            option_sleeve=False,  # Core position
            correlation_data={"SYM": 0.2, "TSLA": 0.1, "WRD": 0.1},
        )
        
        # Should ALLOW or FLAG for existing breach (but not BLOCK the core add)
        self.assertIn(decision.decision, ("ALLOW", "FLAG"))
        self.assertNotEqual(decision.decision, "BLOCK")
    
    def test_sleeve_add_stays_balanced_allows(self):
        """
        Sleeve ADD that stays sleeve ≤ core and ≤ 20% NAV should ALLOW.
        
        Balanced book: core $600, sleeve $100 (10% NAV < 20% limit)
        Add $50 sleeve (5% NAV) → sleeve becomes $150 (15% NAV), still < core $600 → OK
        """
        positions = [
            Position("CORE1", weight_pct=30.0, notional=300, theme="Tech",
                    liquidity_adv=500000000),  # Core
            Position("CORE2", weight_pct=30.0, notional=300, theme="Energy",
                    liquidity_adv=200000000),  # Core
            Position("SLEEVE1", weight_pct=10.0, notional=100, theme="Speculative",
                    liquidity_adv=50000000, option_sleeve=True),  # Sleeve
        ]
        book = Book(nav=1000, cash=300, positions=positions, asof="2026-08-16")
        
        # Verify balance: sleeve $100 (10% NAV), core $600 (60% NAV) → balanced
        self.assertEqual(book.sleeve_notional(), 100)
        self.assertEqual(book.core_notional(), 600)
        self.assertLessEqual(book.sleeve_notional(), book.core_notional())
        
        # Add $50 sleeve (5% NAV) → sleeve becomes $150 (15% NAV < 20%), still < $600 core
        decision = check_book_constraints(
            ticker="SLEEVE2",
            ticket_type="BUY",
            book=book,
            proposed_notional=50,
            theme="Speculative",
            liquidity_adv=40000000,
            option_sleeve=True,
            correlation_data={"CORE1": 0.2, "CORE2": 0.1, "SLEEVE1": 0.3},
        )
        
        # Should ALLOW (stays balanced and under 20% NAV)
        self.assertEqual(decision.decision, "ALLOW")
    
    def test_cio_hold_never_flattened(self):
        """
        CIO-approved HOLD should never be flattened to cure sleeve-core breach.
        
        Even with sleeve > core breach, CIO hold passes through (no flatten).
        """
        positions = [
            Position("CORE", weight_pct=10.0, notional=300, theme="Core",
                    liquidity_adv=100000000),  # Core
            Position("SLEEVE1", weight_pct=15.0, notional=450, theme="Speculative",
                    liquidity_adv=50000000, option_sleeve=True),  # Sleeve
            Position("SLEEVE2", weight_pct=15.0, notional=450, theme="Speculative",
                    liquidity_adv=40000000, hurdle_15pct="miss"),  # Sleeve
        ]
        book = Book(nav=3000, cash=1800, positions=positions, asof="2026-08-16")
        
        # Verify breach: sleeve $900 > core $300
        self.assertEqual(book.sleeve_notional(), 900)
        self.assertEqual(book.core_notional(), 300)
        self.assertGreater(book.sleeve_notional(), book.core_notional())
        
        # CIO-approved HOLD on sleeve position → should FLAG but not flatten
        decision = check_book_constraints(
            ticker="SLEEVE1",
            ticket_type="HOLD",
            book=book,
            cio_approved=True,
        )
        
        # Should FLAG for breach but ALLOW the hold (not flatten)
        self.assertEqual(decision.decision, "FLAG")
        self.assertTrue(decision.cio_approved)
        self.assertTrue(any("sleeve" in r.lower() and "core" in r.lower() for r in decision.reasons))
        self.assertNotEqual(decision.decision, "BLOCK")
    
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
    
    def test_book_option_sleeve_exposure(self):
        """Test option sleeve exposure calculation (marked names only)."""
        positions = [
            Position("SPEC1", weight_pct=8.0, option_sleeve=True),  # Marked
            Position("SPEC2", weight_pct=7.0, hurdle_15pct="miss"),  # Marked
            Position("CORE", weight_pct=10.0),  # Not marked
            Position("GROWTH", weight_pct=5.0, hurdle_15pct="pass"),  # Not marked (pass)
        ]
        book = Book(positions=positions)
        
        # Only SPEC1 and SPEC2 count → 8 + 7 = 15%
        sleeve_exposure = book.option_sleeve_exposure()
        self.assertEqual(sleeve_exposure, 15.0)
    
    def test_position_is_option_sleeve(self):
        """Test Position.is_option_sleeve() logic."""
        # Marked via option_sleeve=True
        pos1 = Position("SPEC1", option_sleeve=True)
        self.assertTrue(pos1.is_option_sleeve())
        
        # Marked via hurdle_15pct="miss"
        pos2 = Position("SPEC2", hurdle_15pct="miss")
        self.assertTrue(pos2.is_option_sleeve())
        
        # Marked via hurdle_15pct="MISS" (case insensitive)
        pos3 = Position("SPEC3", hurdle_15pct="MISS")
        self.assertTrue(pos3.is_option_sleeve())
        
        # Not marked (None)
        pos4 = Position("CORE1")
        self.assertFalse(pos4.is_option_sleeve())
        
        # Not marked (option_sleeve=False)
        pos5 = Position("CORE2", option_sleeve=False)
        self.assertFalse(pos5.is_option_sleeve())
        
        # Not marked (hurdle_15pct="pass")
        pos6 = Position("GROWTH", hurdle_15pct="pass")
        self.assertFalse(pos6.is_option_sleeve())
        
        # Both marked (True takes precedence)
        pos7 = Position("SPEC4", option_sleeve=True, hurdle_15pct="pass")
        self.assertTrue(pos7.is_option_sleeve())


if __name__ == "__main__":
    unittest.main()
