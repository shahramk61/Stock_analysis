# Stock Analysis Skill v4.1 — Advanced Quantitative Signals

**Version:** 4.1
**Last Updated:** 2026-05-10

**Command:** `python scripts/analyze.py TICKER --profile [Balanced|Growth|Value|Momentum] --output [report|json|both]`

### New in v4.1
- Full integration of 5 advanced local signals (IVR, Altman Z-Score, DCF, Earnings Surprise, Rolling Beta)
- Enhanced scoring engine with profile weighting
- Structured JSON output ready for trading bots
- Improved report with advanced signals summary

**Core Capabilities**
- Real yfinance data
- 10,000-path Monte Carlo
- 3-Stage DCF Valuation
- JSON signal files (`signals_TICKER.json`)