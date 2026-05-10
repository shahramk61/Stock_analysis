# Stock Analysis Skill v4.8 — Advanced Quantitative Signals + Monte Carlo Simulations + GPU Deep Learning (Chronos + LSTM + FinBERT + NHITS/TFT Ensemble + PatchTST + Uncertainty)

**Version:** 4.8  
**Last Updated:** 2026-05-10

**Command:** `python scripts/analyze.py TICKER --profile [Balanced|Growth|Value|Momentum] --output [report|json|both]`

**Interactive Dashboard:** `streamlit run scripts/dashboard.py` (recommended for exploration)

### New in v4.8
- **PatchTST** (`get_patchtst_forecast`): Patch Time Series Transformer via NeuralForecast — one of the top-performing SOTA models (2024+ benchmarks often #1). Uses efficient patching for transformer attention on time series. Complements NHITS + TFT ensemble perfectly; added as additional high-quality 5-day forecast signal with its own technicals boost. GPU-accelerated on RTX 5080.
- Updated report to display PatchTST Forecast.
- Updated score.py with PatchTST integration and boost (0.15 weight).
- Bumped to v4.8 with PatchTST as newest DL signal.

### Previous (v4.7)
- **NHITS/TFT Ensemble + Uncertainty** + Interactive Dashboard

**Core Capabilities**
- Real yfinance data
- 10,000-path Monte Carlo price projection (GBM)
- **NEW in 4.8**: PatchTST (SOTA patch-based transformer via NeuralForecast) + NHITS/TFT Ensemble with uncertainty (multi-model DL forecasting flagship)
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
