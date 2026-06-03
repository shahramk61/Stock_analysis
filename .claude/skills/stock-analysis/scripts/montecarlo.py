"""Re-export from canonical scripts/montecarlo.py."""
from _canonical import load_module

_mod = load_module("montecarlo")
run_monte_carlo = _mod.run_monte_carlo