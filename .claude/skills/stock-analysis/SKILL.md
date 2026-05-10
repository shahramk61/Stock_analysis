**Version:** 4.4  
**Last Updated:** 2026-05-10  

**New in v4.4**  
- Momentum signals (6-month & 12-month price momentum + proximity to 52-week high)  
- Gross Profitability (Novy-Marx style: Gross Profit / Total Assets) and Accruals anomaly  
- Integrated into fundamentals (quality) and technicals (momentum) scoring with regime/vol adjustments carried forward  

**Previous (v4.3)**  
- Hidden Markov Model (HMM) for market regime detection (Bull/Neutral/Bear)  
- GARCH(1,1) volatility forecasting for forward-looking risk  

**Previous (v4.2)**  
- Piotroski F-Score (0-9) for earnings quality and financial strength  
- ATR-based Volatility Clustering for risk timing and volatility regime detection  
- Relative Strength vs SPY and Sector for momentum and outperformance context  

**Core Capabilities**  
- Real yfinance data  
- 10,000-path Monte Carlo  
- 3-Stage DCF Valuation  
- JSON signal files (`signals_TICKER.json`)
