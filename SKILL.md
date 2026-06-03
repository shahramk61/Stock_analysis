# Stock Analysis Skill v4.9 — Advanced Quantitative Signals + Monte Carlo Simulations + GPU Deep Learning (Chronos + LSTM + FinBERT + NHITS/TFT/PatchTST Ensemble + Uncertainty)

**Version:** 4.9  
**Last Updated:** 2026-05-11

**Command:** `python scripts/analyze.py TICKER --profile [Balanced|Growth|Value|Momentum] --output [report|json|both]`

**Interactive Dashboard:** `streamlit run scripts/dashboard.py` (recommended for exploration)

### New in v4.9
- **Major Polish & Expansion**:
  - Renamed ensemble to `get_nhits_tft_patchtst_ensemble` (explicitly includes all 3 SOTA models: NHITS + TFT + PatchTST).
  - Added 12+ high-impact quantitative signals: Piotroski F-Score, ATR volatility clustering, Relative Strength vs SPY/Sector, Momentum + 52-week high, Gross Profitability/Accruals (Novy-Marx), HMM Regime Detection, GARCH(1,1) volatility forecast, Amihud Illiquidity, Share Turnover, Volume-Price Correlation, Formulaic Alpha, OBV, Chaikin Money Flow.
  - Refactored GPU signals with shared `_nf_forecast` helper + optional dependency guards.
  - Standardized all emojis (📈 / 📉 / ➕) and cleaned sentiment text.
  - Updated dashboard with per-model metric rows and better error handling.
- Updated requirements.txt with `arch` and `hmmlearn`.
- Resolved version divergence between root `scripts/` and `.claude/skills/` (now consistent).

### Previous (v4.7)
- **NHITS/TFT Ensemble + Uncertainty** + Interactive Dashboard

**Core Capabilities**
- Real yfinance data
- 10,000-path Monte Carlo price projection (GBM)
- **NEW in 4.9**: Full 3-model ensemble (NHITS + TFT + PatchTST) + 12+ new quant signals (Piotroski, GARCH, HMM, liquidity, momentum, etc.)
- **Interactive Streamlit Dashboard** with Plotly visualizations, live controls, and export
- FinBERT news sentiment (GPU accelerated transformer for Sentiment pillar)
- Zero-shot Chronos-2 foundation model forecast (GPU accelerated, no training)
- GPU-accelerated LSTM Deep Learning forecast (PyTorch, RTX 5080 optimized)
- 10,000-path Monte Carlo tail-risk simulation (VaR/CVaR)
- 3-Stage DCF Valuation
- JSON signal files (`signals_TICKER.json`)
- 6-pillar scoring (Fundamentals, Technicals, Valuation, Sentiment, ESG, Risk) + ML boosts to Technicals

**Installation / Usage**
```bash
cd /path/to/stock_analysis_skill
python -m pip install -r requirements.txt
python scripts/analyze.py AAPL --profile Growth
# Or launch the beautiful interactive dashboard:
streamlit run scripts/dashboard.py
```

**Requirements**
- yfinance
- pandas
- numpy
- statsmodels
- tabulate
- **torch** (with CUDA for RTX 5080: see install note in requirements.txt)
- **chronos-forecasting** (for Chronos-2 zero-shot forecasting; installs with torch)
- **transformers** (for FinBERT sentiment; installs with torch)
- **neuralforecast** (for NHITS, TFT, PatchTST SOTA neural forecasting; GPU via torch)
- **arch** (GARCH volatility)
- **hmmlearn** (HMM regime detection)
- streamlit (dashboard)
- plotly (charts)