"""Re-export from canonical scripts/report.py."""
from _canonical import load_module

_mod = load_module("report")
generate_report = _mod.generate_report
generate_json_report = _mod.generate_json_report