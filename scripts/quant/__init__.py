"""
Quant-owned measurement layer for Stock Analysis.

This package provides point-in-time scoring, walk-forward replay, and
hard no-lookahead verification to ensure all measurements are falsifiable
and do not leak future information into historical analysis.

Core modules:
- pit_score: Point-in-time score computation using only asof-sliced data
- walkforward: Walk-forward replay across date ranges
- no_lookahead: Runtime guards and static audit for lookahead detection
- returns_matrix: Point-in-time returns matrix and pairwise correlation
- cli: Command-line interface for running measurements
"""

# Lazy imports to avoid requiring pandas/numpy for audit command
def compute_pit_score(*args, **kwargs):
    from scripts.quant.pit_score import compute_pit_score as _compute_pit_score
    return _compute_pit_score(*args, **kwargs)

def run_walkforward(*args, **kwargs):
    from scripts.quant.walkforward import run_walkforward as _run_walkforward
    return _run_walkforward(*args, **kwargs)

def enable_lookahead_guard():
    from scripts.quant.no_lookahead import enable_lookahead_guard as _enable
    return _enable()

def disable_lookahead_guard():
    from scripts.quant.no_lookahead import disable_lookahead_guard as _disable
    return _disable()

def audit_lookahead_risks(*args, **kwargs):
    from scripts.quant.no_lookahead import audit_lookahead_risks as _audit
    return _audit(*args, **kwargs)

def compute_pit_returns_matrix(*args, **kwargs):
    from scripts.quant.returns_matrix import compute_pit_returns_matrix as _compute
    return _compute(*args, **kwargs)

def compute_pit_pairwise_corr(*args, **kwargs):
    from scripts.quant.returns_matrix import compute_pit_pairwise_corr as _pairwise
    return _pairwise(*args, **kwargs)

__all__ = [
    "compute_pit_score",
    "run_walkforward",
    "enable_lookahead_guard",
    "disable_lookahead_guard",
    "audit_lookahead_risks",
    "compute_pit_returns_matrix",
    "compute_pit_pairwise_corr",
]
