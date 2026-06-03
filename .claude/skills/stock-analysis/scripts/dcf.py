"""Re-export from canonical scripts/dcf.py."""
from _canonical import load_module

_mod = load_module("dcf")
calculate_dcf = _mod.calculate_dcf