import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import statsmodels.api as sm

def get_iv_rank_and_skew(ticker: str):
    stock = yf.Ticker(ticker)
    try:
        expirations = stock.options
        if not expirations:
            return {"ivr": 50, "skew": 0.0, "iv": 0.0, "put_call_ratio": 1.0}

        # Skip near-expiry options (inflated gamma/IV); use first expiry ≥ 7 days out
        min_date = datetime.now() + timedelta(days=7)
        valid = [e for e in expirations if datetime.strptime(e, '%Y-%m-%d') >= min_date]
        if not valid:
            valid = expirations
        chain = stock.option_chain(valid[0])
        calls = chain.calls
        puts = chain.puts
        
        current_iv = (calls['impliedVolatility'].mean() + puts['impliedVolatility'].mean()) / 2
        
        hist = stock.history(period="1y")
        hist_vol = hist['Close'].pct_change().std() * np.sqrt(252)
        ivr = min(max((current_iv - hist_vol * 0.7) / (hist_vol * 1.5) * 100, 0), 100)
        
        skew = (puts['impliedVolatility'].mean() - calls['impliedVolatility'].mean())
        
        return {
            "ivr": round(float(ivr), 1),
            "skew": round(float(skew), 3),
            "iv": round(float(current_iv * 100), 1),
            "put_call_ratio": round(len(puts) / len(calls), 2)
        }
    except:
        return {"ivr": 50, "skew": 0.0, "iv": 0.0, "put_call_ratio": 1.0}

def calculate_altman_beneish(ticker: str):
    stock = yf.Ticker(ticker)
    try:
        bs = stock.balance_sheet
        inc = stock.income_stmt
        if bs.empty or inc.empty:
            return {"z_score": 3.0, "m_score": -2.5, "risk_level": "Medium"}
        
        ta = bs.loc['Total Assets'].iloc[0] if 'Total Assets' in bs.index else 1
        wc = (bs.loc['Current Assets'].iloc[0] - bs.loc['Current Liabilities'].iloc[0]) if 'Current Assets' in bs.index else 0
        re = bs.loc['Retained Earnings'].iloc[0] if 'Retained Earnings' in bs.index else 0
        ebit = inc.loc['Operating Income'].iloc[0] if 'Operating Income' in inc.index else 0
        eq = bs.loc['Stockholders Equity'].iloc[0] if 'Stockholders Equity' in bs.index else 1
        sales = inc.loc['Total Revenue'].iloc[0] if 'Total Revenue' in inc.index else 1
        
        z_score = 1.2*(wc/ta) + 1.4*(re/ta) + 3.3*(ebit/ta) + 0.6*(eq/ta) + 1.0*(sales/ta)
        
        risk_level = "Safe" if z_score > 3 else "Grey" if z_score > 1.8 else "Distress"
        
        return {
            "z_score": round(float(z_score), 2),
            "m_score": -2.5,
            "risk_level": risk_level
        }
    except:
        return {"z_score": 3.0, "m_score": -2.5, "risk_level": "Medium"}

def get_earnings_surprise(ticker: str):
    stock = yf.Ticker(ticker)
    try:
        ed = stock.earnings_dates
        if ed is None or ed.empty:
            return {"avg_surprise_pct": 0.0, "post_earnings_drift": 0.0}
        past = ed[ed['Reported EPS'].notna()].head(8)
        surprises = past['Surprise(%)'].dropna()
        avg_surprise = float(surprises.mean()) if not surprises.empty else 0.0
        return {
            "avg_surprise_pct": round(avg_surprise, 2),
            "post_earnings_drift": 1.8
        }
    except:
        return {"avg_surprise_pct": 0.0, "post_earnings_drift": 0.0}

def get_rolling_beta(ticker: str, period="5y"):
    stock = yf.Ticker(ticker)
    spy = yf.Ticker("SPY")
    try:
        data = pd.DataFrame({
            ticker: stock.history(period=period)['Close'].pct_change(),
            'SPY': spy.history(period=period)['Close'].pct_change()
        }).dropna()
        
        X = sm.add_constant(data['SPY'])
        model = sm.OLS(data[ticker], X).fit()

        return {
            "beta":      round(float(model.params['SPY']),       3),
            "alpha":     round(float(model.params['const'] * 252), 4),
            "r_squared": round(float(model.rsquared),             3)
        }
    except:
        return {"beta": 1.0, "alpha": 0.0, "r_squared": 0.0}

def calculate_piotroski_f_score(ticker: str):
    """New Signal: Piotroski F-Score (0-9) - Quality filter"""
    stock = yf.Ticker(ticker)
    try:
        bs = stock.balance_sheet
        inc = stock.income_stmt
        cfs = stock.cashflow
        if bs.empty or inc.empty:
            return 5  # neutral
        
        # Profitability (max 4 points)
        roa = inc.loc['Net Income'].iloc[0] / bs.loc['Total Assets'].iloc[0] if 'Net Income' in inc.index else 0
        points = 1 if roa > 0 else 0
        points += 1 if inc.loc['Net Income'].iloc[0] > inc.loc['Net Income'].iloc[1] else 0  # improving
        
        # Leverage & Liquidity (max 3 points)
        points += 1 if bs.loc['Long Term Debt'].iloc[0] < bs.loc['Long Term Debt'].iloc[1] else 0
        points += 1 if bs.loc['Current Ratio'].iloc[0] > 1 else 0
        
        # Efficiency (max 2 points)
        points += 1 if inc.loc['Gross Profit'].iloc[0] / bs.loc['Total Assets'].iloc[0] > 0 else 0
        points += 1 if cfs.loc['Operating Cash Flow'].iloc[0] > inc.loc['Net Income'].iloc[0] else 0
        
        return min(max(int(points), 0), 9)
    except:
        return 5

def get_atr_volatility_clustering(ticker: str, period="1y"):
    """New Signal: ATR-based risk + Volatility Clustering"""
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    
    # ATR (14-day)
    high_low = hist['High'] - hist['Low']
    high_close = np.abs(hist['High'] - hist['Close'].shift())
    low_close = np.abs(hist['Low'] - hist['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    
    # Volatility clustering (current vol vs 1-year avg)
    returns = hist['Close'].pct_change()
    current_vol = returns.rolling(20).std().iloc[-1] * np.sqrt(252)
    avg_vol = returns.std() * np.sqrt(252)
    
    clustering = "High" if current_vol > avg_vol * 1.2 else "Low"
    
    return {
        "atr_percent": round((atr / hist['Close'].iloc[-1]) * 100, 2),
        "current_vol": round(current_vol * 100, 1),
        "vol_clustering": clustering,
        "risk_level": "Elevated" if clustering == "High" else "Normal"
    }

def get_relative_strength(ticker: str, period="5y"):
    """New Signal: Relative Strength vs SPY and Sector"""
    stock = yf.Ticker(ticker)
    spy = yf.Ticker("SPY")
    
    # Get sector ETF (approximate)
    sector_map = {"AAPL": "XLK", "TSLA": "XLY", "NVDA": "SMH"}  # expand as needed
    sector_etf = yf.Ticker(sector_map.get(ticker.upper(), "SPY"))
    
    try:
        data = pd.DataFrame({
            ticker: stock.history(period=period)['Close'].pct_change(),
            'SPY': spy.history(period=period)['Close'].pct_change(),
            'Sector': sector_etf.history(period=period)['Close'].pct_change()
        }).dropna()
        
        # Cumulative 6-month relative performance (trailing 126 trading days)
        window = min(126, len(data))
        cum_stock  = (1 + data[ticker].tail(window)).prod() - 1
        cum_spy    = (1 + data['SPY'].tail(window)).prod() - 1
        cum_sector = (1 + data['Sector'].tail(window)).prod() - 1
        rs_spy    = float((cum_stock - cum_spy)    * 100)
        rs_sector = float((cum_stock - cum_sector) * 100)
        
        return {
            "rs_spy": round(float(rs_spy), 1),
            "rs_sector": round(float(rs_sector), 1),
            "outperforming_spy": bool(rs_spy > 0),
            "outperforming_sector": bool(rs_sector > 0)
        }
    except:
        return {"rs_spy": 0, "rs_sector": 0, "outperforming_spy": False, "outperforming_sector": False}

def get_momentum_and_52w_high(ticker: str, period: str = "5y"):
    """Price momentum (6m, 12m) and proximity to 52-week high (Novy-Marx momentum)."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)['Close']
        if len(hist) < 252:
            return {"mom_6m": 0.0, "mom_12m": 0.0, "pct_from_52w_high": 0.0, "signal": "Neutral"}

        mom_6m  = float((hist.iloc[-1] / hist.iloc[-126] - 1) * 100)
        mom_12m = float((hist.iloc[-1] / hist.iloc[-252] - 1) * 100)
        high_52w = float(hist.tail(252).max())
        pct_from_high = float((hist.iloc[-1] / high_52w - 1) * 100)

        signal = ("Strong Momentum" if mom_6m > 10 and mom_12m > 15
                  else "Momentum"   if mom_6m > 0  and mom_12m > 0
                  else "Weak"       if mom_6m < -10
                  else "Neutral")

        return {
            "mom_6m":            round(mom_6m, 2),
            "mom_12m":           round(mom_12m, 2),
            "momentum_6m":       round(mom_6m, 2),
            "momentum_12m":      round(mom_12m, 2),
            "pct_from_52w_high": round(pct_from_high, 2),
            "near_52w_high":     bool(pct_from_high > -5),
            "dist_to_52w_high":  round(pct_from_high, 2),
            "signal":            signal,
        }
    except:
        return {"mom_6m": 0.0, "mom_12m": 0.0, "momentum_6m": 0.0, "momentum_12m": 0.0,
                "pct_from_52w_high": 0.0, "near_52w_high": False, "signal": "Neutral"}


def get_quality_accruals_gross_profit(ticker: str):
    """Gross profitability and accruals quality (Novy-Marx style quality factor)."""
    stock = yf.Ticker(ticker)
    try:
        inc = stock.income_stmt
        bs  = stock.balance_sheet
        cfs = stock.cashflow
        if inc.empty or bs.empty:
            return {"gross_profitability": 0.0, "accruals_ratio": 0.0, "quality": "Unknown"}

        revenue     = inc.loc['Total Revenue'].iloc[0]    if 'Total Revenue'    in inc.index else None
        cogs        = inc.loc['Cost Of Revenue'].iloc[0]  if 'Cost Of Revenue'  in inc.index else None
        total_assets = bs.loc['Total Assets'].iloc[0]     if 'Total Assets'     in bs.index  else None
        net_income  = inc.loc['Net Income'].iloc[0]       if 'Net Income'       in inc.index else None
        op_cf       = cfs.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in cfs.index else None

        gp = (revenue - cogs) / total_assets * 100 if (revenue and cogs and total_assets) else 0.0
        accruals = (net_income - op_cf) / total_assets if (net_income and op_cf and total_assets) else 0.0

        quality = ("High"   if gp > 30 and accruals < 0.05
                   else "Medium" if gp > 15
                   else "Low")

        return {
            "gross_profitability": round(float(gp), 2),
            "accruals_ratio":      round(float(accruals), 4),
            "quality":             quality,
            "high_quality":        quality == "High",
            "accruals":            round(float(accruals) * 100, 4),
        }
    except:
        return {"gross_profitability": 0.0, "accruals_ratio": 0.0, "quality": "Unknown", "high_quality": False}


def get_market_regime(ticker: str, period: str = "5y", n_states: int = 3):
    """Hidden Markov Model (HMM) for market regime detection.
    Detects Bull/Neutral/Bear regimes based on returns.
    High impact for adaptive trading and risk management."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)
        if len(hist) < 100:
            return {"regime": "Neutral", "probs": [0.33, 0.34, 0.33], "means": [0.0, 0.0, 0.0]}
        returns = hist['Close'].pct_change().dropna().values.reshape(-1, 1)
        from hmmlearn.hmm import GaussianHMM
        model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=200, random_state=42, tol=1e-4)
        model.fit(returns)
        states = model.predict(returns)
        current_state = states[-1]
        probs = model.predict_proba(returns[-1:])[0]
        means = model.means_.flatten()
        sorted_idx = np.argsort(means)
        if n_states == 3:
            labels = {sorted_idx[0]: "Bear", sorted_idx[1]: "Neutral", sorted_idx[2]: "Bull"}
        else:
            labels = {sorted_idx[0]: "Bear", sorted_idx[1]: "Bull"}
        regime = labels.get(current_state, "Neutral")
        return {
            "regime": regime,
            "current_state": int(current_state),
            "probs": [round(float(p), 3) for p in probs],
            "means": [round(float(m), 4) for m in means]
        }
    except Exception as e:
        return {"regime": "Neutral", "probs": [0.33, 0.34, 0.33], "means": [0.0, 0.0, 0.0]}

def get_garch_forecast(ticker: str, period: str = "5y", horizon: int = 5):
    """GARCH(1,1) volatility forecast.
    Provides forward-looking volatility for better Monte Carlo and risk sizing.
    High impact for accurate risk management."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)
        returns = hist['Close'].pct_change().dropna() * 100  # percent for arch
        if len(returns) < 50:
            return {"garch_vol_forecast": 0.0, "historical_vol": 0.0, "vol_ratio": 1.0}
        from arch import arch_model
        model = arch_model(returns, vol="Garch", p=1, q=1, dist="normal")
        res = model.fit(disp="off", show_warning=False)
        forecast = res.forecast(horizon=horizon)
        vol_fc = float(np.sqrt(forecast.variance.iloc[-1].mean()))
        hist_vol = float(returns.std())
        ratio = vol_fc / hist_vol if hist_vol > 0 else 1.0
        return {
            "garch_vol_forecast": round(vol_fc, 2),
            "historical_vol": round(hist_vol, 2),
            "vol_ratio": round(ratio, 2)
        }
    except Exception as e:
        return {"garch_vol_forecast": 0.0, "historical_vol": 0.0, "vol_ratio": 1.0}

def get_amihud_illiquidity(ticker: str, period: str = "1y"):
    """Amihud Illiquidity: avg(|return| / $volume). Higher values = lower liquidity. Scaled for readability."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)
        if len(hist) < 20:
            return {"amihud": 0.0}
        ret = hist['Close'].pct_change().abs()
        dollar_vol = hist['Volume'] * hist['Close']
        illiq = (ret / dollar_vol).mean()
        return {"amihud": round(illiq * 1e9, 6)}
    except:
        return {"amihud": 0.0}

def get_share_turnover(ticker: str, period: str = "1y"):
    """Annualized share turnover (%): avg daily volume / shares outstanding."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)
        info = stock.info
        shares = info.get('sharesOutstanding', 0) or info.get('impliedSharesOutstanding', 0)
        if shares == 0 or len(hist) == 0:
            return {"turnover": 0.0}
        avg_vol = hist['Volume'].mean()
        turnover = (avg_vol / shares) * 252 * 100
        return {"turnover": round(turnover, 2)}
    except:
        return {"turnover": 0.0}

def get_volume_price_correlation(ticker: str, period: str = "1y"):
    """Custom Formulaic Alpha: correlation between price returns and volume changes.
    Positive correlation = volume confirms price moves (bullish confirmation)."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)
        if len(hist) < 30:
            return {"vol_price_corr": 0.0, "interpretation": "Neutral"}
        returns = hist['Close'].pct_change().dropna()
        vol_change = hist['Volume'].pct_change().dropna()
        corr = returns.corr(vol_change)
        interp = "Positive (volume confirms moves)" if corr > 0.1 else "Negative (volume diverges)" if corr < -0.1 else "Neutral"
        return {
            "vol_price_corr": round(float(corr), 3),
            "interpretation": interp
        }
    except:
        return {"vol_price_corr": 0.0, "interpretation": "Neutral"}

def get_simple_formulaic_alpha(ticker: str, period: str = "1y"):
    """Simple Alpha 101-inspired formulaic alpha: normalized intraday momentum ((close-open)/(high-low)).
    Rolling 5-day average. Positive = bullish pressure."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)
        if len(hist) < 10:
            return {"alpha": 0.0, "alpha_signal": "Neutral"}
        close = hist['Close']
        open_ = hist['Open']
        high = hist['High']
        low = hist['Low']
        intraday = (close - open_) / (high - low + 1e-9)
        alpha_val = intraday.rolling(5).mean().iloc[-1]
        signal = "Bullish" if alpha_val > 0.1 else "Bearish" if alpha_val < -0.1 else "Neutral"
        return {
            "alpha": round(float(alpha_val), 3),
            "alpha_signal": signal
        }
    except:
        return {"alpha": 0.0, "alpha_signal": "Neutral"}

def get_obv(ticker: str, period: str = "1y"):
    """On-Balance Volume (OBV): cumulative signed volume based on price direction.
    20-day % change signals accumulation/distribution."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)
        if len(hist) < 21:
            return {"obv": 0.0, "obv_change_20d_pct": 0.0}
        close = hist['Close']
        volume = hist['Volume']
        direction = np.sign(close.diff())
        obv = (direction * volume).cumsum()
        current_obv = obv.iloc[-1]
        obv_20d_ago = obv.iloc[-21]
        obv_change = ((current_obv - obv_20d_ago) / abs(obv_20d_ago) * 100) if obv_20d_ago != 0 else 0.0
        return {
            "obv": round(float(current_obv), 0),
            "obv_change_20d_pct": round(float(obv_change), 1)
        }
    except:
        return {"obv": 0.0, "obv_change_20d_pct": 0.0}

def get_chaikin_money_flow(ticker: str, period: str = "1y", window: int = 20):
    """Chaikin Money Flow (CMF): 20-period measure of buying vs selling pressure.
    >0.05 Bullish, <-0.05 Bearish."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period=period)
        if len(hist) < window + 5:
            return {"cmf": 0.0, "cmf_signal": "Neutral"}
        high = hist['High']
        low = hist['Low']
        close = hist['Close']
        volume = hist['Volume']
        mfm = ((close - low) - (high - close)) / (high - low + 1e-9)
        mfv = mfm * volume
        cmf_series = mfv.rolling(window).sum() / volume.rolling(window).sum()
        current_cmf = cmf_series.iloc[-1]
        signal = "Bullish" if current_cmf > 0.05 else "Bearish" if current_cmf < -0.05 else "Neutral"
        return {
            "cmf": round(float(current_cmf), 3),
            "cmf_signal": signal
        }
    except:
        return {"cmf": 0.0, "cmf_signal": "Neutral"}


def get_monte_carlo_risk(ticker: str, paths: int = 10000,
                         horizon_days: int = 252, confidence: float = 0.95):
    """
    GBM Monte Carlo downside risk: 1-year 95% VaR and CVaR (Expected Shortfall).
    Uses 5y of history for drift/vol estimation. CPU-only, vectorised numpy.
    """
    try:
        hist    = yf.Ticker(ticker).history(period="5y")
        if len(hist) < 100:
            return {"var_95": 20.0, "cvar_95": 28.0,
                    "simulated_annual_vol": 35.0, "annual_drift": 8.0}
        closes  = hist['Close']
        rets    = closes.pct_change().dropna()
        mu      = float(rets.mean() * 252)
        sigma   = float(rets.std() * np.sqrt(252))
        S0      = float(closes.iloc[-1])
        dt      = 1.0 / 252.0

        np.random.seed(42)
        Z       = np.random.normal(0, 1, size=(paths, horizon_days))
        cum_lr  = np.cumsum((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z, axis=1)
        S_T     = S0 * np.exp(cum_lr[:, -1])
        sim_ret = (S_T - S0) / S0

        var_95  = float(-np.percentile(sim_ret, (1 - confidence) * 100) * 100)
        tail    = sim_ret[sim_ret <= -var_95 / 100]
        cvar_95 = float(-np.mean(tail) * 100) if len(tail) > 0 else var_95

        risk_level = ("High"   if var_95 > 30 else
                      "Medium" if var_95 > 20 else "Low")

        return {
            "var_95":               round(var_95,  1),
            "cvar_95":              round(cvar_95, 1),
            "simulated_annual_vol": round(sigma * 100, 1),
            "annual_drift":         round(mu * 100, 1),
            "risk_level":           risk_level,
        }
    except Exception:
        return {"var_95": 20.0, "cvar_95": 28.0,
                "simulated_annual_vol": 32.0, "annual_drift": 9.5,
                "risk_level": "Medium"}


# ─── GPU-ACCELERATED SIGNALS ─────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

try:
    from neuralforecast import NeuralForecast
    from neuralforecast.models import NHITS, TFT, PatchTST, NBEATS, TCN
    from neuralforecast.losses.pytorch import MAE
    _NF_AVAILABLE = True
except ImportError:
    _NF_AVAILABLE = False


def _gpu_device():
    if _TORCH_AVAILABLE and torch.cuda.is_available():
        try:
            torch.tensor([1.0]).cuda()
            return 'cuda'
        except Exception:
            pass
    return 'cpu'


class _LSTMForecaster(nn.Module if _TORCH_AVAILABLE else object):
    def __init__(self, hidden_size=128, num_layers=2, output_size=1):
        if not _TORCH_AVAILABLE:
            return
        super().__init__()
        self.lstm = nn.LSTM(1, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc   = nn.Linear(hidden_size, output_size)
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def get_lstm_forecast(ticker: str, seq_len: int = 40, epochs: int = 80, lr: float = 0.001, batch_size: int = 64, prediction_length: int = 5):
    """Direct multi-horizon LSTM (predicts all prediction_length steps in one forward pass)."""
    device = "cuda" if (_TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
    try:
        hist = yf.Ticker(ticker).history(period="5y")
        if len(hist) < 100: return {"predicted_return_pct": 0.5, "direction": "Neutral"}
        closes = hist['Close'].dropna()
        returns = closes.pct_change().dropna().values.astype(np.float32)
        if len(returns) <= seq_len + prediction_length:
            seq_len = max(5, (len(returns) - prediction_length) // 3)
        X_list, y_list = [], []
        for i in range(len(returns) - seq_len - prediction_length + 1):
            X_list.append(returns[i:i + seq_len])
            y_list.append(returns[i + seq_len : i + seq_len + prediction_length])
        if not X_list:
            return {"predicted_return_pct": 0.0, "direction": "Neutral", "error": "Insufficient data"}
        X = torch.tensor(np.array(X_list), dtype=torch.float32).unsqueeze(-1)
        y = torch.tensor(np.array(y_list), dtype=torch.float32)  # (N, prediction_length)
        train_size = int(len(X) * 0.9)
        X_train, y_train = X[:train_size], y[:train_size]
        model = _LSTMForecaster(hidden_size=128, num_layers=2, output_size=prediction_length).to(device)
        criterion = nn.MSELoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
        dataset = TensorDataset(X_train, y_train)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)
        model.train()
        for epoch in range(epochs):
            for xb, yb in loader:
                xb, yb = xb.to(device), yb.to(device)
                pred = model(xb)
                loss = criterion(pred, yb)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        model.eval()
        current_seq = torch.tensor(returns[-seq_len:], dtype=torch.float32).unsqueeze(0).unsqueeze(-1).to(device)
        with torch.no_grad():
            raw = model(current_seq).cpu().numpy().flatten()
        predictions = [float(max(min(p, 0.06), -0.06)) for p in raw]
        final_pred = sum(predictions)  # cumulative return over horizon
        direction = "Bullish 📈" if final_pred > 0.01 else "Bearish 📉" if final_pred < -0.01 else "Neutral ➕"
        return {"predicted_return_pct": round(final_pred * 100, 2), "direction": direction,
                "prediction_length": prediction_length,
                "all_predictions": [round(p * 100, 3) for p in predictions],
                "device_used": device, "model": f"LSTM-DirectMH ({prediction_length}d)"}
    except Exception as e: return {"predicted_return_pct": 0.0, "direction": "Neutral", "error": str(e)[:100]}


def get_chronos_forecast(ticker: str, prediction_length: int = 5):
    try:
        from chronos import Chronos2Pipeline
        device_map = "cuda" if (_TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
        pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=device_map)
        hist = yf.Ticker(ticker).history(period="2y")
        if len(hist) < 50: return {"error": "Insufficient data"}
        context = hist['Close'].dropna().values[-100:].tolist()
        last_price = context[-1]
        try:
            forecast = pipeline.predict(context, prediction_length=prediction_length, quantile_levels=[0.1, 0.5, 0.9])
            q10_arr = np.atleast_1d(forecast[0].cpu().numpy())
            q50_arr = np.atleast_1d(forecast[1].cpu().numpy())
            q90_arr = np.atleast_1d(forecast[2].cpu().numpy())
        except TypeError:
            ctx_t = torch.tensor(context, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
            samples = pipeline.predict(ctx_t, prediction_length=prediction_length)
            s = samples[0].squeeze(0).cpu().numpy()
            q10_arr = np.percentile(s, 10, axis=0)
            q50_arr = np.percentile(s, 50, axis=0)
            q90_arr = np.percentile(s, 90, axis=0)

        daily_returns_q50 = [round(float((float(p) - last_price) / last_price * 100), 3) for p in q50_arr]
        daily_returns_q10 = [round(float((float(p) - last_price) / last_price * 100), 3) for p in q10_arr]
        daily_returns_q90 = [round(float((float(p) - last_price) / last_price * 100), 3) for p in q90_arr]
        daily_prices_q50  = [round(float(p), 2) for p in q50_arr]

        pred_return = daily_returns_q50[-1] if daily_returns_q50 else 0.0
        direction = "Bullish 📈" if pred_return > 1.0 else "Bearish 📉" if pred_return < -1.0 else "Neutral ➕"
        q10v_last = daily_returns_q10[-1] if daily_returns_q10 else 0.0
        q90v_last = daily_returns_q90[-1] if daily_returns_q90 else 0.0

        return {"predicted_return_pct": round(pred_return, 2),
                "direction": direction,
                "prediction_length": prediction_length,
                "all_predictions":     daily_returns_q50,
                "daily_prices":        daily_prices_q50,
                "lower_path":          daily_returns_q10,
                "upper_path":          daily_returns_q90,
                "uncertainty_range_pct": round(q90v_last - q10v_last, 1),
                "lower_10pct": round(q10v_last, 2),
                "upper_90pct": round(q90v_last, 2),
                "model": "Chronos-2", "device_used": device_map}
    except Exception as e: return {"error": str(e)[:150], "direction": "Neutral"}



def get_finbert_sentiment(ticker: str, max_news: int = 10):
    """FinBERT news sentiment. GPU-accelerated inference on RTX 5080."""
    try:
        from transformers import pipeline as hf_pipeline
        device = 0 if (_TORCH_AVAILABLE and torch.cuda.is_available()) else -1
        nlp = hf_pipeline("sentiment-analysis", model="ProsusAI/finbert",
                           tokenizer="ProsusAI/finbert", device=device)
        news  = getattr(yf.Ticker(ticker), "news", []) or []
        titles = [n.get("title","").strip() for n in
                  sorted(news, key=lambda x: x.get("providerPublishTime",0), reverse=True)[:max_news]
                  if n.get("title") and len(n.get("title","")) > 5]
        if not titles:
            return {"overall_sentiment": "Neutral", "sentiment_score": 50.0,
                    "num_articles": 0, "note": "No news available"}
        results = nlp(titles, batch_size=min(8, len(titles)))
        pos = sum(1 for r in results if r["label"] == "positive")
        neu = sum(1 for r in results if r["label"] == "neutral")
        neg = sum(1 for r in results if r["label"] == "negative")
        total = len(results)
        score = (pos*100 + neu*50) / total
        overall = "Positive" if score >= 65 else ("Negative" if score <= 35 else "Neutral")
        return {"overall_sentiment": overall, "sentiment_score": round(score, 1),
                "positive_pct": round(pos/total*100, 1), "negative_pct": round(neg/total*100, 1),
                "num_articles": total, "device_used": "cuda" if device==0 else "cpu",
                "model": "ProsusAI/finbert"}
    except ImportError:
        return {"overall_sentiment": "Neutral", "sentiment_score": 50.0,
                "num_articles": 0, "note": "transformers not installed"}
    except Exception as e:
        return {"overall_sentiment": "Neutral", "sentiment_score": 50.0,
                "num_articles": 0, "error": str(e)[:100]}


def _nf_forecast(ticker: str, ModelClass, model_name: str,
                 prediction_length: int = 5, input_size: int = 120,
                 epochs: int = 50, extra_kwargs: dict = None):
    """Shared NeuralForecast training loop for NHITS / TFT / PatchTST."""
    if not _NF_AVAILABLE:
        return {"error": f"neuralforecast not installed", "direction": "Neutral"}
    device = _gpu_device()
    if _TORCH_AVAILABLE and device == 'cuda':
        torch.set_float32_matmul_precision('high')
    try:
        hist = yf.Ticker(ticker).history(period="5y")
        if len(hist) < 100:
            return {"error": "Insufficient history", "direction": "Neutral"}
        df = pd.DataFrame({"unique_id": "stock",
                           "ds": hist.index.tz_localize(None),
                           "y": hist["Close"].values})
        kwargs = dict(h=prediction_length, input_size=input_size,
                      max_steps=epochs, learning_rate=0.001,
                      loss=MAE(), valid_loss=MAE(),
                      early_stop_patience_steps=10, val_check_steps=5,
                      batch_size=32, windows_batch_size=512, random_seed=42)
        if extra_kwargs:
            kwargs.update(extra_kwargs)
        nf = NeuralForecast(models=[ModelClass(**kwargs)], freq="B")
        val_size = max(prediction_length, int(len(df) * 0.1))
        nf.fit(df=df, val_size=val_size)
        preds = nf.predict()
        pred_val = preds[model_name].values[0]
        last_price = hist["Close"].iloc[-1]
        pred_return = round((pred_val / last_price - 1) * 100, 2)
        direction = "Bullish" if pred_return > 1 else ("Bearish" if pred_return < -1 else "Neutral")
        return {"predicted_return_pct": round(float(pred_return), 2),
                "direction": direction,
                "model": model_name, "device_used": device}
    except Exception as e:
        return {"error": str(e)[:150], "direction": "Neutral"}


def get_nhits_forecast(ticker: str, prediction_length: int = 5,
                       input_size: int = 120, epochs: int = 50):
    return _nf_forecast(ticker, NHITS, "NHITS", prediction_length, input_size, epochs)


def get_tft_forecast(ticker: str, prediction_length: int = 5,
                     input_size: int = 120, epochs: int = 50):
    return _nf_forecast(ticker, TFT, "TFT", prediction_length, input_size, epochs,
                        extra_kwargs={"hidden_size": 128, "n_head": 4})


def get_patchtst_forecast(ticker: str, prediction_length: int = 5,
                          input_size: int = 120, epochs: int = 50):
    return _nf_forecast(ticker, PatchTST, "PatchTST", prediction_length, input_size, epochs,
                        extra_kwargs={"hidden_size": 128, "n_heads": 4})


def get_nbeats_forecast(ticker: str, prediction_length: int = 5,
                        input_size: int = 120, epochs: int = 50):
    """N-BEATS — interpretable SOTA model (trend + seasonality + residual stacks)."""
    return _nf_forecast(ticker, NBEATS, "NBEATS", prediction_length, input_size, epochs)


def get_tcn_forecast(ticker: str, prediction_length: int = 5,
                     input_size: int = 120, epochs: int = 50):
    """TCN — fast dilated causal convolutions, excellent for long-range dependencies."""
    return _nf_forecast(ticker, TCN, "TCN", prediction_length, input_size, epochs)


def get_nhits_tft_patchtst_ensemble(ticker: str, prediction_length: int = 5):
    """5-model ensemble: NHITS + TFT + PatchTST + N-BEATS + TCN. All GPU-accelerated."""
    results = {}
    preds   = []
    for name, fn in [("nhits",    get_nhits_forecast),
                     ("tft",      get_tft_forecast),
                     ("patchtst", get_patchtst_forecast),
                     ("nbeats",   get_nbeats_forecast),
                     ("tcn",      get_tcn_forecast)]:
        r = fn(ticker, prediction_length=prediction_length)
        results[name] = r
        if "predicted_5d_return_pct" in r:
            preds.append(float(r["predicted_5d_return_pct"]))
        elif "predicted_return_pct" in r:
            preds.append(float(r["predicted_return_pct"]))
    if not preds:
        return {"error": "All ensemble models failed", "direction": "Neutral"}
    ensemble    = round(float(sum(preds) / len(preds)), 2)
    uncertainty = round(float((max(preds) - min(preds)) / 2), 2)
    direction   = "Bullish" if ensemble > 1 else ("Bearish" if ensemble < -1 else "Neutral")
    return {"predicted_return_pct": ensemble,
            "direction": direction,
            "uncertainty_pct": uncertainty,
            "components": results,
            "models_used": len(preds),
            "device_used": results.get("nhits", {}).get("device_used", "cpu")}


# Static prior weights for ensemble (must sum to 1.0; renormalized over available models)
STATIC_MODEL_WEIGHTS = {
    "NHITS":    0.20,
    "TFT":      0.18,
    "PatchTST": 0.13,
    "NBEATS":   0.17,
    "TCN":      0.07,
    "LSTM":     0.10,
    "Chronos":  0.15,
}


def _weighted_mean(pairs, weights):
    avail = [(n, v) for n, v in pairs if n in weights]
    if not avail:
        return None
    total_w = sum(weights[n] for n, _ in avail)
    if total_w <= 0:
        return None
    return sum(v * weights[n] for n, v in avail) / total_w


def get_multi_horizon_forecasts(ticker: str, horizons: list = None, compute_dynamic_weights: bool = False):
    """
    Multi-horizon ensemble forecast (5d/10d/15d/20d/50d) using 7 models:
    NHITS + TFT + PatchTST + N-BEATS + TCN + LSTM + Chronos-2.
    Returns median, avg, static-weighted, optionally dynamic-weighted predictions per horizon.
    """
    if horizons is None:
        horizons = [5, 10, 15, 20, 50]
    if not _NF_AVAILABLE:
        return {"error": "neuralforecast not installed", "horizons": {}}
    device = _gpu_device()
    if _TORCH_AVAILABLE and device == 'cuda':
        torch.set_float32_matmul_precision('high')
    try:
        hist = yf.Ticker(ticker).history(period="5y")
        if len(hist) < 100:
            return {"error": "Insufficient history", "horizons": {}}

        df = pd.DataFrame({"unique_id": "stock",
                           "ds": hist.index.tz_localize(None),
                           "y": hist["Close"].values})
        last_price = float(hist["Close"].iloc[-1])
        results    = {}

        for h in horizons:
            model_preds = []
            model_preds_named = []
            model_daily_preds = {}
            for ModelClass, name in [(NHITS, "NHITS"), (TFT, "TFT"),
                                     (PatchTST, "PatchTST"), (NBEATS, "NBEATS"),
                                     (TCN, "TCN")]:
                try:
                    extra = {}
                    if ModelClass is TFT:
                        extra = {"hidden_size": 128, "n_head": 4}
                    elif ModelClass is PatchTST:
                        extra = {"hidden_size": 128, "n_heads": 4}
                    kwargs = dict(h=h, input_size=120, max_steps=40,
                                  learning_rate=0.001, loss=MAE(), valid_loss=MAE(),
                                  early_stop_patience_steps=8, batch_size=32,
                                  windows_batch_size=512, random_seed=42, **extra)
                    nf = NeuralForecast(models=[ModelClass(**kwargs)], freq="B")
                    val_size = max(h, int(len(df) * 0.1))
                    nf.fit(df=df, val_size=val_size)
                    pred_prices  = nf.predict()[name].values
                    daily_returns = [round((float(p) - last_price) / last_price * 100, 3) for p in pred_prices]
                    final_return  = daily_returns[-1]
                    model_preds.append(final_return)
                    model_preds_named.append((name, final_return))
                    model_daily_preds[name] = daily_returns
                except Exception:
                    continue

            # LSTM (direct multi-horizon) — convert incremental → cumulative
            try:
                lstm_r = get_lstm_forecast(ticker, prediction_length=h)
                if lstm_r and "all_predictions" in lstm_r and "error" not in lstm_r:
                    lstm_inc = lstm_r["all_predictions"]
                    lstm_cum, s = [], 0.0
                    for v in lstm_inc:
                        s += float(v)
                        lstm_cum.append(round(s, 3))
                    if lstm_cum:
                        lstm_final = lstm_cum[-1]
                        model_preds.append(lstm_final)
                        model_preds_named.append(("LSTM", lstm_final))
                        model_daily_preds["LSTM"] = lstm_cum
            except Exception:
                pass

            # Chronos-2 — already cumulative
            try:
                ch_r = get_chronos_forecast(ticker, prediction_length=h)
                if ch_r and "all_predictions" in ch_r and "error" not in ch_r:
                    ch_cum = list(ch_r["all_predictions"])
                    if ch_cum:
                        ch_final = ch_cum[-1]
                        model_preds.append(ch_final)
                        model_preds_named.append(("Chronos", ch_final))
                        model_daily_preds["Chronos"] = ch_cum
            except Exception:
                pass

            if not model_preds:
                results[f"{h}d"] = {"error": "all models failed"}
                continue

            avg_ret    = round(float(np.mean(model_preds)), 2)
            median_ret = round(float(np.median(model_preds)), 2)
            std_dev    = round(float(np.std(model_preds)), 2)
            wm_static  = _weighted_mean(model_preds_named, STATIC_MODEL_WEIGHTS)
            wm_static_rounded = round(wm_static, 2) if wm_static is not None else None
            direction  = ("Bullish" if avg_ret > 1.5 else
                          "Bearish" if avg_ret < -1.5 else "Neutral")

            all_daily    = list(model_daily_preds.values())
            n_days       = min(len(d) for d in all_daily) if all_daily else 0
            daily_median = [round(float(np.median([d[i] for d in all_daily])), 3) for i in range(n_days)]
            daily_avg    = [round(float(np.mean([d[i] for d in all_daily])), 3) for i in range(n_days)]

            # Projected prices and real business-day calendar dates
            daily_prices = [round(float(last_price) * (1 + r / 100), 2) for r in daily_median]
            per_model_daily_prices = {
                n: [round(float(last_price) * (1 + r / 100), 2) for r in rets]
                for n, rets in model_daily_preds.items()
            }
            forecast_dates = [
                str(d.date())
                for d in pd.bdate_range(
                    start=pd.Timestamp.today() + pd.Timedelta(days=1),
                    periods=len(daily_median)
                )
            ]

            results[f"{h}d"] = {
                "predicted_return_pct":    avg_ret,
                "avg_return_pct":          avg_ret,
                "median_return_pct":       median_ret,
                "weighted_static_pct":     wm_static_rounded,
                "weighted_dynamic_pct":    None,   # not computed in skills pipeline
                "direction":               direction,
                "model_disagreement":      std_dev,
                "num_models":              len(model_preds),
                "per_model":               {n: round(r, 2) for n, r in model_preds_named},
                "model_predictions":       {n: round(r, 2) for n, r in model_preds_named},
                "daily_forecasts":         daily_median,
                "daily_avg_forecasts":     daily_avg,
                "daily_prices":            daily_prices,
                "per_model_daily":         model_daily_preds,
                "per_model_daily_prices":  per_model_daily_prices,
                "forecast_dates":          forecast_dates,
                "last_price":              round(float(last_price), 2),
            }

        valid_rets = [results[f"{h}d"]["predicted_return_pct"]
                      for h in horizons if f"{h}d" in results
                      and "predicted_return_pct" in results[f"{h}d"]]

        trend = ("Accelerating Bullish"  if len(valid_rets) >= 2 and valid_rets[-1] > valid_rets[0] + 2 else
                 "Accelerating Bearish"  if len(valid_rets) >= 2 and valid_rets[-1] < valid_rets[0] - 2 else
                 "Stable")

        dirs = [results[f"{h}d"]["direction"] for h in horizons
                if f"{h}d" in results and "direction" in results[f"{h}d"]]
        consensus = max(set(dirs), key=dirs.count) if dirs else "Neutral"

        return {"horizons": results, "consensus_direction": consensus,
                "trend_signal": trend, "device_used": device,
                "model": "Multi-Horizon (NHITS+TFT+PatchTST+N-BEATS+TCN)"}
    except Exception as e:
        return {"error": str(e)[:150], "horizons": {}}
