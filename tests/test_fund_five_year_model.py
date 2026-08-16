"""
Tests for five-year model support.

Proves:
- Five-year model returns unavailable when no PIT revenues (never a fabricated revenue path)
- Model refuses to proceed without PIT fundamentals
- Model validates asof integrity (no future leaks)
- Model computes projections from historical revenues when available
"""

from datetime import date

import pytest

from scripts.quant.fund.five_year_model import (
    FiveYearModelResult,
    create_pit_fundamentals_stub,
    evaluate_five_year_model,
)


def test_five_year_model_unavailable_without_pit():
    """Test that five-year model refuses to compute without PIT fundamentals."""
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals=None,  # No PIT store
    )
    
    assert result.is_available is False
    assert "No PIT fundamental store" in result.unavailable_reason
    assert result.projected_revenues is None
    assert result.fair_value is None


def test_five_year_model_unavailable_missing_fields():
    """Test that model refuses incomplete PIT fundamentals."""
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals={
            "ticker": "AAPL",
            # Missing required fields
        },
    )
    
    assert result.is_available is False
    assert "missing required fields" in result.unavailable_reason


def test_five_year_model_detects_future_leak():
    """Test that model detects future data leaks in PIT fundamentals."""
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals={
            "ticker": "AAPL",
            "asof_date": "2023-06-15",  # Future date > asof
            "historical_revenues": [100, 110, 121],
        },
    )
    
    assert result.is_available is False
    assert "future leak" in result.unavailable_reason


def test_five_year_model_insufficient_history():
    """Test that model requires sufficient historical revenues."""
    pit_fundamentals = create_pit_fundamentals_stub(
        ticker="AAPL",
        asof="2023-06-01",
        historical_revenues=[100],  # Only 1 year, need >= 2
    )
    
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals=pit_fundamentals,
    )
    
    assert result.is_available is False
    assert "Insufficient historical revenues" in result.unavailable_reason


def test_five_year_model_computes_from_pit():
    """Test that model computes projections from PIT revenues."""
    # Historical revenues: 10% annual growth
    historical_revenues = [100, 110, 121, 133.1, 146.41]
    
    pit_fundamentals = create_pit_fundamentals_stub(
        ticker="AAPL",
        asof="2023-06-01",
        historical_revenues=historical_revenues,
    )
    
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals=pit_fundamentals,
    )
    
    assert result.is_available is True
    assert result.unavailable_reason is None
    assert result.projected_revenues is not None
    assert len(result.projected_revenues) == 5
    
    # Verify projections are reasonable (continuing growth trend)
    assert result.projected_revenues[0] > historical_revenues[-1]
    
    # Verify asof is correct
    assert result.asof == date(2023, 6, 1)
    assert result.ticker == "AAPL"


def test_five_year_model_handles_negative_growth():
    """Test that model handles declining revenues."""
    # Historical revenues: declining
    historical_revenues = [100, 95, 90]
    
    pit_fundamentals = create_pit_fundamentals_stub(
        ticker="AAPL",
        asof="2023-06-01",
        historical_revenues=historical_revenues,
    )
    
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals=pit_fundamentals,
    )
    
    assert result.is_available is True
    assert result.projected_revenues is not None
    
    # Verify projections continue decline trend
    assert result.projected_revenues[0] < historical_revenues[-1]


def test_five_year_model_caps_growth():
    """Test that model caps extreme growth rates."""
    # Historical revenues: extreme growth (200% per year)
    historical_revenues = [10, 30, 90]
    
    pit_fundamentals = create_pit_fundamentals_stub(
        ticker="AAPL",
        asof="2023-06-01",
        historical_revenues=historical_revenues,
    )
    
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals=pit_fundamentals,
    )
    
    assert result.is_available is True
    
    # Verify growth is capped at reasonable bounds (max 100%)
    # Avg growth would be 200%, capped at 100%
    # So year 1 projection should be 90 * 2 = 180
    assert result.projected_revenues[0] <= 90 * 2.5  # Some margin


def test_five_year_model_result_serialization():
    """Test that model result can be serialized to dict."""
    pit_fundamentals = create_pit_fundamentals_stub(
        ticker="AAPL",
        asof="2023-06-01",
        historical_revenues=[100, 110, 121],
    )
    
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals=pit_fundamentals,
    )
    
    d = result.to_dict()
    assert d["ticker"] == "AAPL"
    assert d["asof"] == "2023-06-01"
    assert d["is_available"] is True
    assert "projected_revenues" in d


def test_five_year_model_never_invents_revenues():
    """Critical test: Model NEVER invents revenues without PIT store."""
    # This test documents the HARD RULE: no PIT store = unavailable, not fabricated
    
    result = evaluate_five_year_model(
        ticker="AAPL",
        asof="2023-06-01",
        pit_fundamentals=None,
    )
    
    # These fields MUST be None when PIT store unavailable
    assert result.projected_revenues is None
    assert result.projected_earnings is None
    assert result.projected_fcf is None
    assert result.terminal_value is None
    assert result.fair_value is None
    
    # Result MUST be marked unavailable
    assert result.is_available is False
    assert result.unavailable_reason is not None
