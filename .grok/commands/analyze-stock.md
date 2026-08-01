---
description: Analyze one or more stocks with weighted scoring, risk management, peer comparison, and multi-horizon recommendations.
---

Use the **stock-analysis** skill to analyze: $ARGUMENTS

Usage:
- Single ticker (e.g. `/analyze-stock AAPL`) — full single-stock report via `python scripts/analyze.py`
- Multiple tickers (e.g. `/analyze-stock AAPL MSFT NVDA`) — side-by-side comparison with ranking and top pick
- No argument — ask the user which stock to analyze

Always run the real pipeline for numbers; do not invent metrics.
