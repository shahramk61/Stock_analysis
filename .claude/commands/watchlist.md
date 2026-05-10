---
description: "Score and rank a list of tickers using the stock-analysis skill. Usage: /watchlist TICKER1 TICKER2 ... Outputs a ranked table with composite scores, ratings, and one-line theses."
allowed-tools: Read, Write, Bash, WebFetch, WebSearch, Skill
---

Use the **stock-analysis** skill to run a condensed watchlist analysis on: $ARGUMENTS

Score each stock using fundamentals + valuation pillars (fast mode), then output a ranked table:

| Rank | Ticker | Score | Rating | Thesis | 🚩 Flags |
|---|---|---|---|---|---|

Sort by composite score descending. Flag any risk disqualifiers. End with a "Top 3 Picks" summary.

If no tickers are provided, ask the user for their watchlist.
