"""
Asof marking utilities for Quant fund tools.

Every score, conviction, ticket state, and model output must carry asof (date) and source.
If a field cannot be marked asof-safe, it is unavailable.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AsofMark:
    """
    Immutable asof mark for a measurement.
    
    Every measurement must carry:
    - asof: The date at which this measurement was computed (data available <= asof)
    - source: The data source or computation method
    - value: The actual measurement value (None if unavailable)
    - unavailable_reason: Why the value is unavailable (if applicable)
    """
    
    asof: date
    source: str
    value: Any = None
    unavailable_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate asof mark integrity."""
        if not isinstance(self.asof, date):
            raise ValueError(f"asof must be a date, got {type(self.asof)}")
        if not self.source:
            raise ValueError("source must be specified")
        if self.value is None and not self.unavailable_reason:
            raise ValueError("unavailable_reason must be provided when value is None")
    
    @property
    def is_available(self) -> bool:
        """Check if this measurement is available (computed)."""
        return self.value is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "asof": str(self.asof),
            "source": self.source,
            "value": self.value,
            "is_available": self.is_available,
            "unavailable_reason": self.unavailable_reason,
        }


def mark_asof(
    value: Any,
    asof: date | str | datetime,
    source: str,
    unavailable_reason: Optional[str] = None,
) -> AsofMark:
    """
    Create an asof mark for a measurement.
    
    Args:
        value: The measurement value (None if unavailable)
        asof: As-of date (YYYY-MM-DD or date or datetime)
        source: Data source or computation method
        unavailable_reason: Why the value is unavailable (if applicable)
    
    Returns:
        AsofMark instance
    """
    if isinstance(asof, str):
        asof_date = datetime.strptime(asof, "%Y-%m-%d").date()
    elif isinstance(asof, datetime):
        asof_date = asof.date()
    else:
        asof_date = asof
    
    return AsofMark(
        asof=asof_date,
        source=source,
        value=value,
        unavailable_reason=unavailable_reason,
    )


def validate_asof(mark: AsofMark, max_asof: date) -> bool:
    """
    Validate that an asof mark is not leaking future data.
    
    Args:
        mark: The asof mark to validate
        max_asof: The maximum allowed asof date
    
    Returns:
        True if valid (mark.asof <= max_asof), False if leaking
    """
    return mark.asof <= max_asof


def mark_unavailable(
    asof: date | str | datetime,
    source: str,
    reason: str,
) -> AsofMark:
    """
    Create an unavailable asof mark.
    
    Args:
        asof: As-of date
        source: Data source or computation method
        reason: Why the value is unavailable
    
    Returns:
        AsofMark with value=None and unavailable_reason set
    """
    return mark_asof(
        value=None,
        asof=asof,
        source=source,
        unavailable_reason=reason,
    )
