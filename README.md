# Stock Analysis v5.0 - Signal Generator for Trading Bot

Canonical pipeline code lives in `scripts/` (signals, scoring, reports, dashboard). The Claude skill under `.claude/skills/stock-analysis/` re-exports from there.

## Usage
```bash
python scripts/analyze.py AAPL --output json --profile Balanced
streamlit run scripts/dashboard.py
python test_quant_analyst.py
```

## Future
Structured JSON output is intended for a separate trading bot via Trading API.