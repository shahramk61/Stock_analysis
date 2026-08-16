"""
Fund-level book constraint limits for Shahram's thematic paper fund.

These limits define the guardrails for liquidity, concentration, cash management,
name/theme purity, and whether a ticket would break the book.

Updated: August 2026 - Book constraint model (VaR flatten retired)
"""

from typing import Final

# Cash constraints
MIN_CASH_PCT: Final[float] = 10.0  # Minimum cash as % of NAV
MAX_CASH_PCT: Final[float] = 100.0  # Maximum cash as % of NAV

# Position concentration limits
MAX_SINGLE_NAME_PCT: Final[float] = 10.0  # Max single position as % of NAV
MAX_SECTOR_THEME_PCT: Final[float] = 25.0  # Max sector/theme as % of NAV
MAX_FACTOR_CLUSTER_PCT: Final[float] = 35.0  # Max correlated factor cluster as % of NAV

# Portfolio construction limits
MAX_NAMES: Final[int] = 20  # Maximum number of positions in the book
MIN_NAMES: Final[int] = 1   # Minimum number of positions (avoid empty book)

# Liquidity requirements
# Note: Specific ADV (Average Daily Volume) thresholds should be defined
# based on position size and expected holding period. Fail closed if missing.
MIN_LIQUIDITY_ADV_MULTIPLIER: Final[float] = 20.0  # Position should be < ADV/20 for liquid exit

# Theme purity
# Each position must have a theme tag that aligns with fund mandate
REQUIRE_THEME_TAG: Final[bool] = True

# Correlation requirements for factor cluster checks
# First add of a name doesn't require correlation data
# Multi-name ADD requires correlation for cluster validation
REQUIRE_CORR_FOR_MULTI_NAME_ADD: Final[bool] = True

# Stranded book thresholds (for TRIM/SELL flagging)
# Flag if a SELL would leave cash below this absolute minimum
STRANDED_CASH_FLOOR_PCT: Final[float] = 5.0

# Flag if a SELL would leave fewer than this many names
STRANDED_MIN_NAMES: Final[int] = 3

# Flag if a SELL would create a liquidity hole (e.g., remaining positions too illiquid)
STRANDED_LIQUIDITY_CHECK: Final[bool] = True


def get_limits_summary() -> dict:
    """Return a dictionary of all limit constants for logging/debugging."""
    return {
        "min_cash_pct": MIN_CASH_PCT,
        "max_cash_pct": MAX_CASH_PCT,
        "max_single_name_pct": MAX_SINGLE_NAME_PCT,
        "max_sector_theme_pct": MAX_SECTOR_THEME_PCT,
        "max_factor_cluster_pct": MAX_FACTOR_CLUSTER_PCT,
        "max_names": MAX_NAMES,
        "min_names": MIN_NAMES,
        "min_liquidity_adv_multiplier": MIN_LIQUIDITY_ADV_MULTIPLIER,
        "require_theme_tag": REQUIRE_THEME_TAG,
        "require_corr_for_multi_name_add": REQUIRE_CORR_FOR_MULTI_NAME_ADD,
        "stranded_cash_floor_pct": STRANDED_CASH_FLOOR_PCT,
        "stranded_min_names": STRANDED_MIN_NAMES,
        "stranded_liquidity_check": STRANDED_LIQUIDITY_CHECK,
    }
