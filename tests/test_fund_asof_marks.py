"""
Tests for asof marking utilities.

Proves:
- Asof marks are immutable and carry date + source
- Unavailable values require reason
- Validation catches future leaks
"""

from datetime import date, timedelta

import pytest

from scripts.quant.fund.asof_marks import (
    AsofMark,
    mark_asof,
    mark_unavailable,
    validate_asof,
)


def test_asof_mark_creation():
    """Test creating asof marks with valid data."""
    asof_date = date(2023, 6, 1)
    mark = mark_asof(
        value=100.5,
        asof=asof_date,
        source="hist_close",
    )
    
    assert mark.asof == asof_date
    assert mark.source == "hist_close"
    assert mark.value == 100.5
    assert mark.is_available is True
    assert mark.unavailable_reason is None


def test_asof_mark_from_string_date():
    """Test creating asof marks from string dates."""
    mark = mark_asof(
        value=200.0,
        asof="2023-07-15",
        source="pit_score",
    )
    
    assert mark.asof == date(2023, 7, 15)
    assert mark.value == 200.0


def test_asof_mark_unavailable():
    """Test creating unavailable asof marks."""
    mark = mark_unavailable(
        asof="2023-06-01",
        source="mc_risk",
        reason="insufficient hist for MC simulation",
    )
    
    assert mark.is_available is False
    assert mark.value is None
    assert mark.unavailable_reason == "insufficient hist for MC simulation"


def test_asof_mark_validation_fails_without_reason():
    """Test that unavailable marks require a reason."""
    with pytest.raises(ValueError, match="unavailable_reason must be provided"):
        AsofMark(
            asof=date(2023, 6, 1),
            source="test",
            value=None,
            unavailable_reason=None,
        )


def test_asof_mark_validation_fails_without_source():
    """Test that marks require a source."""
    with pytest.raises(ValueError, match="source must be specified"):
        AsofMark(
            asof=date(2023, 6, 1),
            source="",
            value=100.0,
        )


def test_asof_mark_validation_fails_with_wrong_type():
    """Test that asof must be a date."""
    with pytest.raises(ValueError, match="asof must be a date"):
        AsofMark(
            asof="2023-06-01",  # String not allowed directly
            source="test",
            value=100.0,
        )


def test_validate_asof_no_leak():
    """Test validating asof marks against max_asof (no leak)."""
    mark = mark_asof(
        value=100.0,
        asof="2023-06-01",
        source="test",
    )
    
    max_asof = date(2023, 6, 15)
    assert validate_asof(mark, max_asof) is True


def test_validate_asof_detects_leak():
    """Test validating asof marks detects future leaks."""
    mark = mark_asof(
        value=100.0,
        asof="2023-06-15",
        source="test",
    )
    
    max_asof = date(2023, 6, 1)
    assert validate_asof(mark, max_asof) is False


def test_asof_mark_to_dict():
    """Test serializing asof marks to dict."""
    mark = mark_asof(
        value=100.5,
        asof="2023-06-01",
        source="hist_close",
    )
    
    d = mark.to_dict()
    assert d["asof"] == "2023-06-01"
    assert d["source"] == "hist_close"
    assert d["value"] == 100.5
    assert d["is_available"] is True
    assert d["unavailable_reason"] is None


def test_asof_mark_immutable():
    """Test that asof marks are immutable."""
    mark = mark_asof(
        value=100.0,
        asof="2023-06-01",
        source="test",
    )
    
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        mark.value = 200.0
    
    with pytest.raises(Exception):
        mark.asof = date(2023, 6, 2)


def test_mark_unavailable_convenience():
    """Test mark_unavailable convenience function."""
    mark = mark_unavailable(
        asof="2023-06-01",
        source="five_year_model",
        reason="no PIT revenue store",
    )
    
    assert mark.is_available is False
    assert mark.unavailable_reason == "no PIT revenue store"
    
    d = mark.to_dict()
    assert d["is_available"] is False
    assert d["unavailable_reason"] == "no PIT revenue store"
