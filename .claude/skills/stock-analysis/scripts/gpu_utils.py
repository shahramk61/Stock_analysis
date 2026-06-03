"""Re-export from canonical scripts/gpu_utils.py."""
from _canonical import load_module

_mod = load_module("gpu_utils")
gpu_available = _mod.gpu_available