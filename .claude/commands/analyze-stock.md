---
description: Analyze one or more stocks using the weighted scoring model with risk management, peer comparison, and multi-horizon recommendations. Usage: /analyze-stock TICKER [TICKER2 TICKER3 ...]
allowed-tools: Read, Write, Bash, WebFetch, WebSearch, Skill
---

Use the **stock-analysis** skill to analyze the following ticker(s): $ARGUMENTS

- If a single ticker is provided, run a full single-stock analysis.
- If multiple tickers are provided (e.g. AAPL MSFT NVDA), run a multi-stock comparison: score each stock, build a ranking table, and identify the top pick.
- If no ticker is provided, ask the user which stock(s) they want to analyze.
