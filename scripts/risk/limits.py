"""
Risk-ratified concentration limits.

Authority: Risk CoS. Do not invent other limits.

These limits are used by the concentration check in gate.py.
When a concentration check fires, these limits appear in the risk_veto object.
"""

# Risk-ratified concentration limits
CONCENTRATION_LIMITS = {
    "single_name_pct": 0.10,      # single name ≤ 10% of book
    "sector_pct": 0.25,            # sector ≤ 25%
    "factor_cluster_pct": 0.35,    # factor cluster ≤ 35%
    "min_cash_pct": 0.10,          # cash ≥ 10%
    "max_names": 20,               # max 20 names
}

# Ratified limits that cannot be enforced yet (awaiting Quant PIT data)
PENDING_ENFORCEMENT = {
    "factor_cluster": "Awaiting Quant PIT return matrix or explicit PIT factor tags",
    "correlation": "Awaiting Quant PIT return matrix",
}
