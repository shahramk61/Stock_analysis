"""
CIO Conviction/Score Tracker for Quant fund tools.

Read-only ledger the CIO can consume: per name (and optional theme tag) the latest
asof-safe overall score, availability ledger, last_print (Close <= asof only),
mc_risk.var_95/cvar_95 if computed else unavailable.

Time series of those marks (walk-forward of scores), not a live peek.

Does NOT emit BUY/SELL. Does NOT invent conviction. If conviction is derived from
existing quantitative_conviction / score bands, the rule is stated and only applied
to computed scores. If cannot compute, conviction is unavailable.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.quant.fund.asof_marks import AsofMark, mark_asof, mark_unavailable
from scripts.quant.pit_score import compute_pit_score


@dataclass
class TrackerEntry:
    """
    Single tracker entry for a name at a specific asof date.
    
    All fields are asof-safe: computed from data available <= asof.
    """
    
    ticker: str
    asof: date
    theme: Optional[str] = None  # Theme tag supplied by others, never invented
    overall_score: Optional[float] = None
    pillar_scores: Optional[Dict[str, float]] = None
    last_print: Optional[float] = None
    last_print_date: Optional[str] = None
    last_print_source: str = "hist_close_asof"
    var_95: Optional[float] = None
    cvar_95: Optional[float] = None
    availability: Dict[str, str] = field(default_factory=dict)
    conviction: Optional[str] = None  # Derived from score bands if computed, else unavailable
    conviction_rule: Optional[str] = None  # Rule used to derive conviction
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ticker": self.ticker,
            "asof": str(self.asof),
            "theme": self.theme,
            "overall_score": self.overall_score,
            "pillar_scores": self.pillar_scores,
            "last_print": self.last_print,
            "last_print_date": self.last_print_date,
            "last_print_source": self.last_print_source,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "availability": self.availability,
            "conviction": self.conviction,
            "conviction_rule": self.conviction_rule,
        }


@dataclass
class CIOTracker:
    """
    CIO Tracker: Read-only ledger of asof-safe scores and convictions.
    
    Time series of tracker entries, not a live peek.
    """
    
    entries: List[TrackerEntry] = field(default_factory=list)
    
    def add_entry(self, entry: TrackerEntry):
        """Add a tracker entry (asof must be >= last entry asof)."""
        if self.entries and entry.asof < self.entries[-1].asof:
            raise ValueError(
                f"Asof dates must be non-decreasing: "
                f"{entry.asof} < {self.entries[-1].asof}"
            )
        self.entries.append(entry)
    
    def get_latest(self, ticker: str) -> Optional[TrackerEntry]:
        """Get the latest tracker entry for a ticker."""
        ticker_entries = [e for e in self.entries if e.ticker == ticker]
        return ticker_entries[-1] if ticker_entries else None
    
    def get_time_series(
        self,
        ticker: Optional[str] = None,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> List[TrackerEntry]:
        """
        Get time series of tracker entries.
        
        Args:
            ticker: Filter by ticker (None = all tickers)
            start: Filter by asof >= start (None = no start filter)
            end: Filter by asof <= end (None = no end filter)
        
        Returns:
            List of tracker entries matching filters
        """
        filtered = self.entries
        
        if ticker:
            filtered = [e for e in filtered if e.ticker == ticker]
        if start:
            filtered = [e for e in filtered if e.asof >= start]
        if end:
            filtered = [e for e in filtered if e.asof <= end]
        
        return filtered
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "num_entries": len(self.entries),
            "tickers": list({e.ticker for e in self.entries}),
        }
    
    def save(self, path: str | Path):
        """Save tracker to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: str | Path) -> "CIOTracker":
        """Load tracker from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        
        tracker = cls()
        for entry_dict in data["entries"]:
            entry = TrackerEntry(
                ticker=entry_dict["ticker"],
                asof=datetime.strptime(entry_dict["asof"], "%Y-%m-%d").date(),
                theme=entry_dict.get("theme"),
                overall_score=entry_dict.get("overall_score"),
                pillar_scores=entry_dict.get("pillar_scores"),
                last_print=entry_dict.get("last_print"),
                last_print_date=entry_dict.get("last_print_date"),
                last_print_source=entry_dict.get("last_print_source", "hist_close_asof"),
                var_95=entry_dict.get("var_95"),
                cvar_95=entry_dict.get("cvar_95"),
                availability=entry_dict.get("availability", {}),
                conviction=entry_dict.get("conviction"),
                conviction_rule=entry_dict.get("conviction_rule"),
            )
            tracker.add_entry(entry)
        
        return tracker


def derive_conviction(score: Optional[float]) -> tuple[Optional[str], Optional[str]]:
    """
    Derive conviction from quantitative score bands.
    
    Rule: Only applied to computed scores, never invented.
    - score >= 75: "High"
    - 60 <= score < 75: "Medium"
    - score < 60: "Low"
    - score is None: unavailable
    
    Returns:
        (conviction, rule_description)
    """
    if score is None:
        return None, None
    
    rule = "score_bands: High>=75, Medium>=60, Low<60"
    
    if score >= 75:
        return "High", rule
    elif score >= 60:
        return "Medium", rule
    else:
        return "Low", rule


def create_tracker_entry_from_pit_score(
    pit_result: Dict[str, Any],
    theme: Optional[str] = None,
) -> TrackerEntry:
    """
    Create a tracker entry from a PIT score result.
    
    Args:
        pit_result: Result from compute_pit_score()
        theme: Optional theme tag (supplied by others, not invented)
    
    Returns:
        TrackerEntry with asof-safe fields populated
    """
    asof_str = pit_result["asof"]
    asof_date = datetime.strptime(asof_str, "%Y-%m-%d").date()
    
    overall_score = pit_result.get("overall_score")
    conviction, conviction_rule = derive_conviction(overall_score)
    
    # Extract mc_risk if available and computed (not placeholder)
    var_95 = None
    cvar_95 = None
    signals = pit_result.get("signals", {})
    mc_risk = signals.get("mc_risk", {})
    availability = pit_result.get("availability", {})
    
    if availability.get("mc_risk") == "computed":
        var_95 = mc_risk.get("var_95")
        cvar_95 = mc_risk.get("cvar_95")
    
    return TrackerEntry(
        ticker=pit_result["ticker"],
        asof=asof_date,
        theme=theme,
        overall_score=overall_score,
        pillar_scores=pit_result.get("pillar_scores"),
        last_print=pit_result.get("last_print"),
        last_print_date=pit_result.get("last_print_date"),
        last_print_source=pit_result.get("last_print_source", "hist_close_asof"),
        var_95=var_95,
        cvar_95=cvar_95,
        availability=availability,
        conviction=conviction,
        conviction_rule=conviction_rule,
    )


def get_latest_tracker_state(
    tickers: List[str],
    asof: date | str | datetime,
    hist_dict: Dict[str, Any],
    theme_dict: Optional[Dict[str, str]] = None,
    profile: str = "Balanced",
) -> CIOTracker:
    """
    Get latest tracker state for a list of tickers at a specific asof date.
    
    Args:
        tickers: List of ticker symbols
        asof: As-of date for the tracker state
        hist_dict: Dictionary mapping ticker -> OHLCV DataFrame
        theme_dict: Optional dictionary mapping ticker -> theme tag
        profile: Scoring profile (default "Balanced")
    
    Returns:
        CIOTracker with one entry per ticker at the specified asof
    """
    if isinstance(asof, str):
        asof_date = datetime.strptime(asof, "%Y-%m-%d").date()
    elif isinstance(asof, datetime):
        asof_date = asof.date()
    else:
        asof_date = asof
    
    tracker = CIOTracker()
    theme_dict = theme_dict or {}
    
    for ticker in tickers:
        hist = hist_dict.get(ticker)
        if hist is None:
            # Cannot compute score without hist
            continue
        
        pit_result = compute_pit_score(
            ticker=ticker,
            asof=asof_date,
            hist=hist,
            profile=profile,
            use_forecasts=False,
        )
        
        if "error" in pit_result:
            # Skip tickers with errors
            continue
        
        entry = create_tracker_entry_from_pit_score(
            pit_result,
            theme=theme_dict.get(ticker),
        )
        tracker.add_entry(entry)
    
    return tracker


def get_tracker_time_series(
    tickers: List[str],
    start: date | str | datetime,
    end: date | str | datetime,
    hist_dict: Dict[str, Any],
    theme_dict: Optional[Dict[str, str]] = None,
    profile: str = "Balanced",
    rebalance_days: int = 20,
) -> CIOTracker:
    """
    Get tracker time series for a list of tickers over a date range.
    
    Walk-forward computation of tracker entries at each rebalance point.
    
    Args:
        tickers: List of ticker symbols
        start: Start date
        end: End date
        hist_dict: Dictionary mapping ticker -> OHLCV DataFrame (must cover full range)
        theme_dict: Optional dictionary mapping ticker -> theme tag
        profile: Scoring profile (default "Balanced")
        rebalance_days: Number of trading days between rebalances
    
    Returns:
        CIOTracker with time series of entries for all tickers
    """
    import pandas as pd
    from scripts.quant.walkforward import run_walkforward
    
    if isinstance(start, str):
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
    elif isinstance(start, datetime):
        start_date = start.date()
    else:
        start_date = start
    
    if isinstance(end, str):
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    elif isinstance(end, datetime):
        end_date = end.date()
    else:
        end_date = end
    
    tracker = CIOTracker()
    theme_dict = theme_dict or {}
    
    for ticker in tickers:
        hist = hist_dict.get(ticker)
        if hist is None:
            continue
        
        # Run walk-forward for this ticker
        wf_result = run_walkforward(
            ticker=ticker,
            start=start_date,
            end=end_date,
            hist=hist,
            rebalance_days=rebalance_days,
            profile=profile,
            use_forecasts=False,
            attach_realized_returns=False,
        )
        
        if "error" in wf_result:
            continue
        
        # Convert each walk-forward step to a tracker entry
        for step in wf_result["steps"]:
            asof_str = step["asof"]
            asof_date = datetime.strptime(asof_str, "%Y-%m-%d").date()
            
            overall_score = step.get("score")
            conviction, conviction_rule = derive_conviction(overall_score)
            
            # Extract mc_risk if available
            var_95 = None
            cvar_95 = None
            signals = step.get("signals", {})
            mc_risk = signals.get("mc_risk", {}) if signals else {}
            availability = step.get("availability", {})
            
            if availability.get("mc_risk") == "computed":
                var_95 = mc_risk.get("var_95")
                cvar_95 = mc_risk.get("cvar_95")
            
            entry = TrackerEntry(
                ticker=ticker,
                asof=asof_date,
                theme=theme_dict.get(ticker),
                overall_score=overall_score,
                pillar_scores=step.get("pillar_scores"),
                last_print=step.get("last_print"),
                last_print_date=step.get("last_print_date"),
                last_print_source=step.get("last_print_source", "hist_close_asof"),
                var_95=var_95,
                cvar_95=cvar_95,
                availability=availability,
                conviction=conviction,
                conviction_rule=conviction_rule,
            )
            tracker.add_entry(entry)
    
    return tracker
