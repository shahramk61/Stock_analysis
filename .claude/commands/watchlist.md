---
description: Score and rank a list of stock tickers by composite score with ratings and risk flags.
allowed-tools: Read, Write, Bash, WebFetch, WebSearch, Skill
---

Use the **stock-analysis** skill to run a condensed watchlist analysis on: $ARGUMENTS

Score each stock using fundamentals and valuation pillars (fast mode), then output a ranked table sorted by composite score. Flag any risk disqualifiers. End with a Top 3 Picks summary.

If no tickers are provided, ask the user for their watchlist.
