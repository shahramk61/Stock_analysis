"""Re-export from canonical scripts/stock_signals.py."""
from _canonical import load_module

_mod = load_module("stock_signals", "stock_signals.py")
globals().update({k: v for k, v in _mod.__dict__.items() if not k.startswith("_")})