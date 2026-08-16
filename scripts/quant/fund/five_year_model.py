"""
Five-year model support for Quant fund tools.

Honest five-year model evaluation: ONLY from asof-safe inputs (historical
revenues/fundamentals that were known <= asof).

If there is no PIT fundamental/revenue store, do NOT invent revenues and do NOT
pull live yfinance financials. Mark 5-year model outputs unavailable and say why.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from scripts.quant.fund.asof_marks import AsofMark, mark_asof, mark_unavailable


@dataclass
class FiveYearModelResult:
    """
    Result of five-year model evaluation.
    
    All fields are asof-safe: computed from data available <= asof.
    If fundamentals are not available PIT, outputs are unavailable.
    """
    
    ticker: str
    asof: date
    is_available: bool
    unavailable_reason: Optional[str] = None
    
    # Model outputs (None if unavailable)
    projected_revenues: Optional[List[float]] = None
    projected_earnings: Optional[List[float]] = None
    projected_fcf: Optional[List[float]] = None
    terminal_value: Optional[float] = None
    fair_value: Optional[float] = None
    
    # Metadata
    model_version: Optional[str] = None
    inputs_used: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ticker": self.ticker,
            "asof": str(self.asof),
            "is_available": self.is_available,
            "unavailable_reason": self.unavailable_reason,
            "projected_revenues": self.projected_revenues,
            "projected_earnings": self.projected_earnings,
            "projected_fcf": self.projected_fcf,
            "terminal_value": self.terminal_value,
            "fair_value": self.fair_value,
            "model_version": self.model_version,
            "inputs_used": self.inputs_used,
        }


def evaluate_five_year_model(
    ticker: str,
    asof: date | str | datetime,
    pit_fundamentals: Optional[Dict[str, Any]] = None,
    model_config: Optional[Dict[str, Any]] = None,
) -> FiveYearModelResult:
    """
    Evaluate a five-year projection model at a specific asof date.
    
    HONEST IMPLEMENTATION: Only uses asof-safe inputs. If PIT fundamentals are not
    available, returns unavailable result with clear reason.
    
    Args:
        ticker: Stock ticker symbol
        asof: As-of date for the evaluation
        pit_fundamentals: Point-in-time fundamental data (historical revenues/financials
                          known <= asof). If None, model cannot be evaluated.
        model_config: Optional model configuration (growth rates, discount rate, etc.)
    
    Returns:
        FiveYearModelResult with outputs or unavailable status
    """
    if isinstance(asof, str):
        asof_date = datetime.strptime(asof, "%Y-%m-%d").date()
    elif isinstance(asof, datetime):
        asof_date = asof.date()
    else:
        asof_date = asof
    
    # CRITICAL: Refuse to proceed if no PIT fundamentals available
    if pit_fundamentals is None:
        return FiveYearModelResult(
            ticker=ticker,
            asof=asof_date,
            is_available=False,
            unavailable_reason="No PIT fundamental store available. "
                               "Cannot compute 5-year model without historical revenues.",
        )
    
    # Validate PIT fundamentals have required fields
    required_fields = ["historical_revenues", "asof_date"]
    missing_fields = [f for f in required_fields if f not in pit_fundamentals]
    if missing_fields:
        return FiveYearModelResult(
            ticker=ticker,
            asof=asof_date,
            is_available=False,
            unavailable_reason=f"PIT fundamentals missing required fields: {missing_fields}",
        )
    
    # Validate PIT fundamentals asof_date <= asof (no future leakage)
    pit_asof_str = pit_fundamentals.get("asof_date")
    if pit_asof_str:
        pit_asof = datetime.strptime(pit_asof_str, "%Y-%m-%d").date()
        if pit_asof > asof_date:
            return FiveYearModelResult(
                ticker=ticker,
                asof=asof_date,
                is_available=False,
                unavailable_reason=f"PIT fundamentals asof {pit_asof} > evaluation asof {asof_date} (future leak)",
            )
    
    # If we reach here, PIT fundamentals are available and valid
    # Compute 5-year projections from historical revenues
    
    historical_revenues = pit_fundamentals.get("historical_revenues", [])
    if not historical_revenues or len(historical_revenues) < 2:
        return FiveYearModelResult(
            ticker=ticker,
            asof=asof_date,
            is_available=False,
            unavailable_reason="Insufficient historical revenues for projection (need >= 2 years)",
        )
    
    # Simple growth model: use average historical growth rate
    # This is a stub - real implementation would use more sophisticated model
    model_config = model_config or {}
    
    # Compute historical growth rate
    revenue_growth_rates = []
    for i in range(1, len(historical_revenues)):
        prev_rev = historical_revenues[i - 1]
        curr_rev = historical_revenues[i]
        if prev_rev > 0:
            growth = (curr_rev - prev_rev) / prev_rev
            revenue_growth_rates.append(growth)
    
    if not revenue_growth_rates:
        return FiveYearModelResult(
            ticker=ticker,
            asof=asof_date,
            is_available=False,
            unavailable_reason="Cannot compute growth rate from historical revenues",
        )
    
    avg_growth = sum(revenue_growth_rates) / len(revenue_growth_rates)
    
    # Cap growth at reasonable bounds (-50% to +100%)
    avg_growth = max(-0.5, min(1.0, avg_growth))
    
    # Project 5 years forward
    last_revenue = historical_revenues[-1]
    projected_revenues = []
    for year in range(1, 6):
        projected_rev = last_revenue * ((1 + avg_growth) ** year)
        projected_revenues.append(round(projected_rev, 2))
    
    # Stub: Earnings and FCF projections
    # Real implementation would use margin assumptions, capex, working capital, etc.
    # For now, mark as unavailable
    projected_earnings = None
    projected_fcf = None
    
    # Stub: Terminal value and fair value
    # Real implementation would discount FCF and add terminal value
    terminal_value = None
    fair_value = None
    
    return FiveYearModelResult(
        ticker=ticker,
        asof=asof_date,
        is_available=True,
        unavailable_reason=None,
        projected_revenues=projected_revenues,
        projected_earnings=projected_earnings,
        projected_fcf=projected_fcf,
        terminal_value=terminal_value,
        fair_value=fair_value,
        model_version="simple_growth_v1",
        inputs_used={
            "historical_revenues": historical_revenues,
            "avg_growth": round(avg_growth, 4),
            "projection_years": 5,
        },
    )


def create_pit_fundamentals_stub(
    ticker: str,
    asof: date | str | datetime,
    historical_revenues: List[float],
) -> Dict[str, Any]:
    """
    Create a PIT fundamentals stub for testing.
    
    This is a helper for tests. Real implementation would query a PIT fundamental store.
    
    Args:
        ticker: Stock ticker symbol
        asof: As-of date for the fundamentals
        historical_revenues: List of historical annual revenues (most recent last)
    
    Returns:
        Dictionary with PIT fundamental data
    """
    if isinstance(asof, str):
        asof_date = datetime.strptime(asof, "%Y-%m-%d").date()
    elif isinstance(asof, datetime):
        asof_date = asof.date()
    else:
        asof_date = asof
    
    return {
        "ticker": ticker,
        "asof_date": str(asof_date),
        "historical_revenues": historical_revenues,
    }
