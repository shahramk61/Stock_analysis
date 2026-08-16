"""
Hard no-lookahead guards and audit for Quant measurement tools.

Runtime guards intercept live yfinance fundamental accesses during replay.
Static audit scans code for known leaking helpers.
"""

import ast
import inspect
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, List, Tuple

# Thread-local guard state
_guard_state = threading.local()


def _is_guard_enabled() -> bool:
    return getattr(_guard_state, "enabled", False)


def enable_lookahead_guard():
    """Enable runtime guard against live fundamental fetches."""
    _guard_state.enabled = True


def disable_lookahead_guard():
    """Disable runtime guard."""
    _guard_state.enabled = False


@contextmanager
def lookahead_guard():
    """Context manager for guarded execution."""
    enable_lookahead_guard()
    try:
        yield
    finally:
        disable_lookahead_guard()


class LookaheadViolation(Exception):
    """Raised when live fundamental access is detected during guarded replay."""

    pass


def _guard_fundamental_access(method_name: str, caller_frame=None):
    """Check if a fundamental access should fail."""
    if not _is_guard_enabled():
        return

    # Get caller info for better error messages
    if caller_frame is None:
        import inspect

        caller_frame = inspect.currentframe().f_back.f_back

    caller_file = caller_frame.f_code.co_filename if caller_frame else "unknown"
    caller_line = caller_frame.f_lineno if caller_frame else 0
    caller_func = caller_frame.f_code.co_name if caller_frame else "unknown"

    raise LookaheadViolation(
        f"LOOKAHEAD VIOLATION: {method_name} accessed during guarded replay. "
        f"Called from {caller_file}:{caller_line} in {caller_func}(). "
        f"Use pre-sliced hist= and empty info dict for point-in-time replay."
    )


def patch_yfinance_guards():
    """
    Monkey-patch yfinance Ticker to guard fundamental accesses.

    This is invasive but necessary to catch leaks at runtime.
    Call this once before running PIT scoring or walk-forward.
    """
    try:
        import yfinance as yf
    except ImportError:
        return  # yfinance not installed, no patching needed

    original_ticker_init = yf.Ticker.__init__

    def guarded_init(self, ticker, *args, **kwargs):
        original_ticker_init(self, ticker, *args, **kwargs)

        # Store original methods
        if not hasattr(self, "_quant_originals"):
            self._quant_originals = {}

        # Guard fundamental property accesses
        for attr in [
            "info",
            "financials",
            "balance_sheet",
            "cashflow",
            "earnings",
            "quarterly_financials",
            "quarterly_balance_sheet",
            "quarterly_cashflow",
            "earnings_dates",
            "get_info",
        ]:
            if hasattr(self, attr):
                original = getattr(self, attr)
                self._quant_originals[attr] = original

                if callable(original):

                    def make_guarded_method(name, orig):
                        def guarded(*args, **kwargs):
                            _guard_fundamental_access(f"Ticker.{name}()")
                            return orig(*args, **kwargs)

                        return guarded

                    setattr(self, attr, make_guarded_method(attr, original))
                else:
                    # Property: wrap with guard check
                    def make_guarded_property(name, orig_attr):
                        @property
                        def guarded(self):
                            _guard_fundamental_access(f"Ticker.{name}")
                            return orig_attr

                        return guarded

                    # Replace the property
                    prop = make_guarded_property(attr, original)
                    setattr(type(self), f"_guarded_{attr}", prop)

    yf.Ticker.__init__ = guarded_init


def audit_lookahead_risks(
    scan_paths: List[str] = None,
) -> Tuple[List[dict], List[dict]]:
    """
    Static audit: scan Python files for known leaking patterns.

    Returns:
        (fundamental_leaks, info_dict_leaks)
        Each leak is a dict with: file, line, pattern, context
    """
    if scan_paths is None:
        # Default: scan scripts/
        repo_root = Path(__file__).parent.parent.parent
        scan_paths = [
            str(repo_root / "scripts" / "score.py"),
            str(repo_root / "scripts" / "signals.py"),
            str(repo_root / "scripts" / "stock_signals.py"),
            str(repo_root / "scripts" / "dcf.py"),
        ]

    fundamental_leaks = []
    info_dict_leaks = []

    # Known leaking helpers (no hist/asof params)
    leaking_funcs = [
        "calculate_altman_beneish",
        "get_earnings_surprise",
        "calculate_piotroski_f_score",
        "get_quality_accruals_gross_profit",
        "get_finbert_sentiment",
    ]

    # yfinance fundamental attributes
    yf_fundamental_attrs = [
        "balance_sheet",
        "cashflow",
        "earnings",
        "quarterly_financials",
        "quarterly_balance_sheet",
        "quarterly_cashflow",
        "earnings_dates",
        "income_stmt",
    ]

    # info dict accesses (live fundamentals)
    info_getters = ["info.get", "info["]

    for path in scan_paths:
        if not os.path.exists(path):
            continue

        try:
            with open(path, "r") as f:
                source = f.read()
                lines = source.splitlines()
        except Exception:
            continue

        # Parse AST
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            continue

        # Look for function calls to known leaking helpers
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in leaking_funcs:
                    # Check if hist= or asof= is passed
                    has_hist = any(
                        kw.arg in ("hist", "asof") for kw in node.keywords
                    )
                    if not has_hist:
                        lineno = node.lineno
                        context = lines[lineno - 1] if lineno <= len(lines) else ""
                        fundamental_leaks.append(
                            {
                                "file": path,
                                "line": lineno,
                                "pattern": f"{func_name}() without hist/asof",
                                "context": context.strip(),
                            }
                        )

            # Look for yfinance fundamental attribute accesses
            if isinstance(node, ast.Attribute):
                if node.attr in yf_fundamental_attrs:
                    lineno = node.lineno
                    context = lines[lineno - 1] if lineno <= len(lines) else ""
                    fundamental_leaks.append(
                        {
                            "file": path,
                            "line": lineno,
                            "pattern": f".{node.attr} (yfinance fundamental)",
                            "context": context.strip(),
                        }
                    )

        # Simple text search for info.get / info[ patterns
        for i, line in enumerate(lines, start=1):
            for pattern in info_getters:
                if pattern in line and "info" in line:
                    # Skip comments
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    info_dict_leaks.append(
                        {
                            "file": path,
                            "line": i,
                            "pattern": "info dict access (live fundamental)",
                            "context": stripped,
                        }
                    )
                    break

    return fundamental_leaks, info_dict_leaks


def print_audit_report(fundamental_leaks: List[dict], info_dict_leaks: List[dict]):
    """Print a human-readable audit report."""
    print("\n" + "=" * 80)
    print("QUANT NO-LOOKAHEAD AUDIT REPORT")
    print("=" * 80)

    if fundamental_leaks:
        print(f"\n⚠️  Found {len(fundamental_leaks)} fundamental leak(s):\n")
        for leak in fundamental_leaks:
            print(f"  {leak['file']}:{leak['line']}")
            print(f"    Pattern: {leak['pattern']}")
            print(f"    Context: {leak['context']}")
            print()
    else:
        print("\n✓ No fundamental leaks detected (known helpers).")

    if info_dict_leaks:
        print(f"\n⚠️  Found {len(info_dict_leaks)} info dict access(es):\n")
        for leak in info_dict_leaks:
            print(f"  {leak['file']}:{leak['line']}")
            print(f"    Pattern: {leak['pattern']}")
            print(f"    Context: {leak['context']}")
            print()
    else:
        print("\n✓ No info dict leaks detected.")

    print("=" * 80)
    print(
        "NOTE: Detection is heuristic. Review each finding to confirm it affects replay."
    )
    print("=" * 80 + "\n")
