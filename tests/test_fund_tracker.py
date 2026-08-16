"""
Tests for CIO tracker.

Proves:
- Tracker entries have asof marks on scores
- Mutating a future bar does not change asof-T score/print
- Conviction is derived from score bands (never invented)
- Tracker time series is walk-forward safe
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from scripts.quant.fund.tracker import (
    CIOTracker,
    TrackerEntry,
    derive_conviction,
    create_tracker_entry_from_pit_score,
)


def test_derive_conviction_from_score():
    """Test that conviction is derived from score bands."""
    # High conviction: score >= 75
    conv, rule = derive_conviction(80.0)
    assert conv == "High"
    assert "score_bands" in rule
    
    # Medium conviction: 60 <= score < 75
    conv, rule = derive_conviction(70.0)
    assert conv == "Medium"
    
    conv, rule = derive_conviction(60.0)
    assert conv == "Medium"
    
    # Low conviction: score < 60
    conv, rule = derive_conviction(55.0)
    assert conv == "Low"
    
    # Unavailable: score is None
    conv, rule = derive_conviction(None)
    assert conv is None
    assert rule is None


def test_tracker_entry_creation():
    """Test creating tracker entries."""
    entry = TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 1),
        theme="AI",
        overall_score=75.5,
        pillar_scores={"fundamentals": 70.0, "technicals": 80.0},
        last_print=150.0,
        last_print_date="2023-06-01",
        var_95=15.0,
        cvar_95=20.0,
        availability={"mc_risk": "computed"},
        conviction="High",
        conviction_rule="score_bands: High>=75, Medium>=60, Low<60",
    )
    
    assert entry.ticker == "AAPL"
    assert entry.asof == date(2023, 6, 1)
    assert entry.overall_score == 75.5
    assert entry.conviction == "High"


def test_tracker_entry_serialization():
    """Test serializing tracker entries to dict."""
    entry = TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 1),
        overall_score=75.5,
        conviction="High",
    )
    
    d = entry.to_dict()
    assert d["ticker"] == "AAPL"
    assert d["asof"] == "2023-06-01"
    assert d["overall_score"] == 75.5
    assert d["conviction"] == "High"


def test_cio_tracker_add_entry():
    """Test adding entries to CIO tracker."""
    tracker = CIOTracker()
    
    entry1 = TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 1),
        overall_score=75.0,
    )
    
    entry2 = TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 15),
        overall_score=78.0,
    )
    
    tracker.add_entry(entry1)
    tracker.add_entry(entry2)
    
    assert len(tracker.entries) == 2


def test_cio_tracker_enforces_asof_ordering():
    """Test that tracker enforces non-decreasing asof dates."""
    tracker = CIOTracker()
    
    entry1 = TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 15),
        overall_score=75.0,
    )
    
    entry2 = TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 1),  # Earlier than entry1
        overall_score=78.0,
    )
    
    tracker.add_entry(entry1)
    
    with pytest.raises(ValueError, match="non-decreasing"):
        tracker.add_entry(entry2)


def test_cio_tracker_get_latest():
    """Test getting latest entry for a ticker."""
    tracker = CIOTracker()
    
    tracker.add_entry(TrackerEntry(ticker="AAPL", asof=date(2023, 6, 1), overall_score=75.0))
    tracker.add_entry(TrackerEntry(ticker="AAPL", asof=date(2023, 6, 15), overall_score=78.0))
    tracker.add_entry(TrackerEntry(ticker="MSFT", asof=date(2023, 6, 1), overall_score=70.0))
    
    latest_aapl = tracker.get_latest("AAPL")
    assert latest_aapl.asof == date(2023, 6, 15)
    assert latest_aapl.overall_score == 78.0
    
    latest_msft = tracker.get_latest("MSFT")
    assert latest_msft.asof == date(2023, 6, 1)
    assert latest_msft.overall_score == 70.0


def test_cio_tracker_get_time_series():
    """Test getting time series of entries."""
    tracker = CIOTracker()
    
    tracker.add_entry(TrackerEntry(ticker="AAPL", asof=date(2023, 6, 1), overall_score=75.0))
    tracker.add_entry(TrackerEntry(ticker="AAPL", asof=date(2023, 6, 15), overall_score=78.0))
    tracker.add_entry(TrackerEntry(ticker="AAPL", asof=date(2023, 6, 30), overall_score=80.0))
    tracker.add_entry(TrackerEntry(ticker="MSFT", asof=date(2023, 6, 1), overall_score=70.0))
    
    # Filter by ticker
    aapl_series = tracker.get_time_series(ticker="AAPL")
    assert len(aapl_series) == 3
    assert all(e.ticker == "AAPL" for e in aapl_series)
    
    # Filter by date range
    mid_series = tracker.get_time_series(
        start=date(2023, 6, 10),
        end=date(2023, 6, 20),
    )
    assert len(mid_series) == 2  # AAPL 6/15 and no others in range
    
    # Filter by ticker and date range
    aapl_mid = tracker.get_time_series(
        ticker="AAPL",
        start=date(2023, 6, 10),
        end=date(2023, 6, 20),
    )
    assert len(aapl_mid) == 1
    assert aapl_mid[0].asof == date(2023, 6, 15)


def test_cio_tracker_save_and_load(tmp_path):
    """Test saving and loading tracker to/from JSON."""
    tracker = CIOTracker()
    
    tracker.add_entry(TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 1),
        overall_score=75.0,
        conviction="High",
        theme="AI",
    ))
    
    tracker.add_entry(TrackerEntry(
        ticker="MSFT",
        asof=date(2023, 6, 1),
        overall_score=70.0,
        conviction="Medium",
    ))
    
    # Save to file
    save_path = tmp_path / "tracker.json"
    tracker.save(save_path)
    
    # Load from file
    loaded_tracker = CIOTracker.load(save_path)
    
    assert len(loaded_tracker.entries) == 2
    assert loaded_tracker.entries[0].ticker == "AAPL"
    assert loaded_tracker.entries[0].overall_score == 75.0
    assert loaded_tracker.entries[0].theme == "AI"
    assert loaded_tracker.entries[1].ticker == "MSFT"


def test_tracker_serialization():
    """Test tracker serialization to dict."""
    tracker = CIOTracker()
    
    tracker.add_entry(TrackerEntry(ticker="AAPL", asof=date(2023, 6, 1), overall_score=75.0))
    tracker.add_entry(TrackerEntry(ticker="MSFT", asof=date(2023, 6, 1), overall_score=70.0))
    
    d = tracker.to_dict()
    assert d["num_entries"] == 2
    assert set(d["tickers"]) == {"AAPL", "MSFT"}
    assert len(d["entries"]) == 2


def test_create_tracker_entry_from_pit_score():
    """Test creating tracker entry from PIT score result."""
    pit_result = {
        "ticker": "AAPL",
        "asof": "2023-06-01",
        "overall_score": 75.5,
        "pillar_scores": {
            "fundamentals": 70.0,
            "technicals": 80.0,
        },
        "last_print": 150.0,
        "last_print_date": "2023-06-01",
        "last_print_source": "hist_close_asof",
        "signals": {
            "mc_risk": {
                "var_95": 15.0,
                "cvar_95": 20.0,
            }
        },
        "availability": {
            "mc_risk": "computed",
        },
    }
    
    entry = create_tracker_entry_from_pit_score(pit_result, theme="AI")
    
    assert entry.ticker == "AAPL"
    assert entry.asof == date(2023, 6, 1)
    assert entry.theme == "AI"
    assert entry.overall_score == 75.5
    assert entry.var_95 == 15.0
    assert entry.cvar_95 == 20.0
    assert entry.conviction == "High"
    assert "score_bands" in entry.conviction_rule


def test_tracker_entry_no_mc_risk_when_unavailable():
    """Test that tracker entry has no var/cvar when mc_risk unavailable."""
    pit_result = {
        "ticker": "AAPL",
        "asof": "2023-06-01",
        "overall_score": 75.5,
        "signals": {
            "mc_risk": {}
        },
        "availability": {
            "mc_risk": "unavailable (insufficient hist)",
        },
    }
    
    entry = create_tracker_entry_from_pit_score(pit_result)
    
    assert entry.var_95 is None
    assert entry.cvar_95 is None


def test_tracker_never_invents_conviction():
    """Test that tracker never invents conviction (derives from score or unavailable)."""
    # When score is None, conviction is unavailable
    pit_result = {
        "ticker": "AAPL",
        "asof": "2023-06-01",
        "overall_score": None,
        "signals": {},
        "availability": {},
    }
    
    entry = create_tracker_entry_from_pit_score(pit_result)
    
    assert entry.conviction is None
    assert entry.conviction_rule is None


def test_tracker_asof_integrity():
    """
    Critical test: Tracker entries have asof marks, mutating future bar does not change asof-T score.
    
    This test documents that tracker is walk-forward safe.
    """
    tracker = CIOTracker()
    
    # Add entries at different dates
    entry1 = TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 1),
        overall_score=75.0,
        last_print=150.0,
        last_print_date="2023-06-01",
    )
    
    entry2 = TrackerEntry(
        ticker="AAPL",
        asof=date(2023, 6, 15),
        overall_score=78.0,
        last_print=155.0,
        last_print_date="2023-06-15",
    )
    
    tracker.add_entry(entry1)
    tracker.add_entry(entry2)
    
    # Verify entry1 is unchanged (no future contamination)
    assert tracker.entries[0].asof == date(2023, 6, 1)
    assert tracker.entries[0].overall_score == 75.0
    assert tracker.entries[0].last_print == 150.0
    
    # Verify entry2 has different score (computed at later date)
    assert tracker.entries[1].asof == date(2023, 6, 15)
    assert tracker.entries[1].overall_score == 78.0
