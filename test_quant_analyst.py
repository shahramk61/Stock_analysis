#!/usr/bin/env python3
"""Smoke test for the Quantitative Analyst agent.

Exercises:
- Core data provider report
- Structured signals output
- Conviction + warnings
- v2 debate stub (via debate_mode=True; also works when llm is passed in real usage)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from agents.quantitative_analyst.quantitative_analyst import create_quantitative_analyst

print("=== Quantitative Analyst Smoke Test (v2 polish) ===\n")

# v1 style (data provider only)
quant_node = create_quantitative_analyst()
state = {"ticker": "AAPL", "company_of_interest": "AAPL", "messages": []}
result = quant_node(state)

print("--- Report (first 1200 chars) ---")
report = result.get("quantitative_report", "No report")
print(report[:1200] + ("...\n" if len(report) > 1200 else "\n"))

print("--- Structured outputs ---")
print("Conviction:", result.get("quantitative_conviction"))
print("Warnings:", result.get("quantitative_warnings", []))
print("Debate commentary (empty in pure v1):", repr(result.get("quantitative_debate_commentary", ""))[:200])

sigs = result.get("quantitative_signals", {})
print("Signals keys:", list(sigs.keys()))
print("Regime from signals:", sigs.get("regime", {}).get("regime"))
print("Consensus from ensemble:", sigs.get("multi_horizon", {}).get("consensus_direction"))
print("Schema valid:", sigs.get("schema_valid"), "version:", sigs.get("schema_version"))
if sigs.get("schema_errors"):
    print("Schema errors:", sigs.get("schema_errors"))

print("\n--- v2 debate stub (explicit debate_mode) ---")
quant_node_v2 = create_quantitative_analyst(debate_mode=True)
result_v2 = quant_node_v2({"ticker": "AAPL", "company_of_interest": "AAPL", "messages": [], "use_forecasts": False})
print("Debate note:", result_v2.get("quantitative_debate_commentary", "")[:500])
print("Conviction:", result_v2.get("quantitative_conviction"))
var = (result_v2.get("quantitative_signals") or {}).get("risk", {}).get("var_95")
print("VaR95:", var)
if var is not None and float(var) > 20:
    assert "VaR" in (result_v2.get("quantitative_debate_commentary") or ""), "elevated VaR must appear in debate"