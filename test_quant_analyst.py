#!/usr/bin/env python3
"""Smoke test for the Quantitative Analyst agent."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from agents.quantitative_analyst.quantitative_analyst import create_quantitative_analyst

quant_node = create_quantitative_analyst()

state = {
    "ticker": "AAPL",
    "company_of_interest": "AAPL",
    "messages": [],
}

result = quant_node(state)

print("=== Quantitative Analyst Output ===\n")
print(result.get("quantitative_report", "No report generated"))