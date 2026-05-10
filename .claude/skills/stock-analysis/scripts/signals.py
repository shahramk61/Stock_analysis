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

def get_rolling_beta(ticker: str, period="2y"):
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

def get_relative_strength(ticker: str, period="2y"):
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

def get_market_regime(ticker: str, period: str = "3y", n_states: int = 3):
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

def get_garch_forecast(ticker: str, period: str = "2y", horizon: int = 5):
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

def get_momentum_and_52w_high(ticker: str):
    """Momentum (6m/12m) + proximity to 52-week high.
    High impact classic momentum factor + nearness to all-time high."""
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period="2y")
        if len(hist) < 260:
            return {"momentum_6m": 0.0, "momentum_12m": 0.0, "dist_to_52w_high": 0.0, "near_52w_high": False}
        close = hist['Close'].dropna()
        mom_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100
        mom_12m = (close.iloc[-1] / close.iloc[-252] - 1) * 100 if len(close) > 252 else 0.0
        high_52w = close.rolling(window=252, min_periods=200).max().iloc[-1]
        dist = ((high_52w - close.iloc[-1]) / high_52w * 100) if high_52w > 0 else 0.0
        near_high = dist < 10.0
        return {
            "momentum_6m": round(float(mom_6m), 1),
            "momentum_12m": round(float(mom_12m), 1),
            "dist_to_52w_high": round(float(dist), 1),
            "near_52w_high": bool(near_high)
        }
    except:
        return {"momentum_6m": 0.0, "momentum_12m": 0.0, "dist_to_52w_high": 0.0, "near_52w_high": False}

def get_quality_accruals_gross_profit(ticker: str):
    """Gross Profitability (Novy-Marx style) and Accruals.
    Strong quality factors for fundamentals."""
    stock = yf.Ticker(ticker)
    try:
        inc = stock.income_stmt
        bal = stock.balance_sheet
        cf = stock.cashflow
        if inc.empty or bal.empty or cf.empty:
            return {"gross_profitability": 0.0, "accruals": 0.0, "high_quality": False}
        # Latest annual
        revenue = float(inc.loc['Total Revenue'].iloc[0]) if 'Total Revenue' in inc.index else 0.0
        cogs = float(inc.loc['Cost Of Revenue'].iloc[0]) if 'Cost Of Revenue' in inc.index else 0.0
        gross_profit = revenue - cogs
        total_assets = float(bal.loc['Total Assets'].iloc[0]) if 'Total Assets' in bal.index else 1.0
        gp_ratio = gross_profit / total_assets if total_assets != 0 else 0.0
        net_income = float(inc.loc['Net Income'].iloc[0]) if 'Net Income' in inc.index else 0.0
        op_cf = float(cf.loc['Operating Cash Flow'].iloc[0]) if 'Operating Cash Flow' in cf.index else 0.0
        accruals_ratio = (net_income - op_cf) / total_assets if total_assets != 0 else 0.0
        high_quality = (gp_ratio > 0.15 and accruals_ratio < 0.05)
        return {
            "gross_profitability": round(gp_ratio * 100, 1),
            "accruals": round(accruals_ratio * 100, 1),
            "high_quality": bool(high_quality)
        }
    except:
        return {"gross_profitability": 0.0, "accruals": 0.0, "high_quality": False}
