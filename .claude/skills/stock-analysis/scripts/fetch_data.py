"""Re-export from canonical scripts/fetch_data.py."""
from _canonical import load_module

_mod = load_module("fetch_data")
fetch_stock_data = _mod.fetch_stock_data