**Version:** 4.5  
**Last Updated:** 2026-05-10  

**New in v4.5**  
- Amihud Illiquidity measure (avg |return| / $volume)  
- Share Turnover (annualized volume / shares outstanding)  
- Liquidity boosts integrated into fundamentals scoring  

**Previous (v4.4)**  
- Momentum signals (6-month & 12-month price momentum + proximity to 52-week high)  
- Gross Profitability (Novy-Marx style: Gross Profit / Total Assets) and Accruals anomaly  

**Previous (v4.3)**  
- Hidden Markov Model (HMM) for market regime detection (Bull/Neutral/Bear)  
- GARCH(1,1) volatility forecasting for forward-looking risk  

**Core Capabilities**  
- Real yfinance data  
- 10,000-path Monte Carlo  
- 3-Stage DCF Valuation  
- JSON signal files (`signals_TICKER.json`)
