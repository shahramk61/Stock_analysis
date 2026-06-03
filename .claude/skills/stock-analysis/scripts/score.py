"""Re-export from canonical scripts/score.py."""
from _canonical import load_module

_mod = load_module("score")
calculate_pillars = _mod.calculate_pillars