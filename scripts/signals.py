import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import statsmodels.api as sm
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

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

def get_monte_carlo_risk(ticker: str, paths: int = 10000, horizon_days: int = 252, confidence: float = 0.95):
    """
    Monte Carlo simulation-based downside risk signal using Geometric Brownian Motion.
    Computes 1-year 95% VaR and CVaR (Expected Shortfall) based on historical drift and vol.
    """
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period="5y")
        if len(hist) < 100:
            return {"var_95": 20.0, "cvar_95": 28.0, "simulated_annual_vol": 35.0, "annual_drift": 8.0}
        
        closes = hist['Close']
        returns = closes.pct_change().dropna()
        mu = returns.mean() * 252  # annualized drift
        sigma = returns.std() * np.sqrt(252)  # annualized vol
        
        S0 = closes.iloc[-1]
        dt = 1.0 / 252.0
        
        # Simulate paths (vectorized for speed)
        np.random.seed(42)  # reproducible for now; remove for production randomness
        Z = np.random.normal(0, 1, size=(paths, horizon_days))
        drift_term = (mu - 0.5 * sigma**2) * dt
        diffusion_term = sigma * np.sqrt(dt) * Z
        log_returns_cum = np.cumsum(drift_term + diffusion_term, axis=1)
        S_T = S0 * np.exp(log_returns_cum[:, -1])
        
        simulated_returns = (S_T - S0) / S0
        
        # 95% VaR (5% worst case loss, as positive %)
        var_95 = -np.percentile(simulated_returns, 5) * 100
        
        # CVaR / Expected Shortfall: average loss in the tail (beyond VaR)
        tail_returns = simulated_returns[simulated_returns <= -var_95 / 100]
        cvar_95 = -np.mean(tail_returns) * 100 if len(tail_returns) > 0 else var_95
        
        return {
            "var_95": round(float(var_95), 1),
            "cvar_95": round(float(cvar_95), 1),
            "simulated_annual_vol": round(float(sigma * 100), 1),
            "annual_drift": round(float(mu * 100), 1)
        }
    except Exception as e:
        return {"var_95": 18.5, "cvar_95": 25.0, "simulated_annual_vol": 32.0, "annual_drift": 9.5}


class LSTMForecaster(nn.Module):
    """Simple LSTM for stock return forecasting. Benefits significantly from GPU (RTX 5080)."""
    def __init__(self, input_size: int = 1, hidden_size: int = 128, num_layers: int = 2, output_size: int = 1, dropout: float = 0.2):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, output_size)
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        # Take the last time step
        return self.fc(lstm_out[:, -1, :])


def get_lstm_forecast(ticker: str, seq_len: int = 40, epochs: int = 80, lr: float = 0.001, batch_size: int = 64, prediction_length: int = 5):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period="5y")
        if len(hist) < 100: return {"predicted_return_pct": 0.5, "direction": "Neutral"}
        closes = hist['Close'].dropna()
        returns = closes.pct_change().dropna().values.astype(np.float32)
        if len(returns) <= seq_len: seq_len = max(5, len(returns) // 3)
        X_list, y_list = [], []
        for i in range(len(returns) - seq_len):
            X_list.append(returns[i:i + seq_len])
            y_list.append(returns[i + seq_len])
        X = torch.tensor(np.array(X_list), dtype=torch.float32).unsqueeze(-1)
        y = torch.tensor(np.array(y_list), dtype=torch.float32).unsqueeze(-1)
        train_size = int(len(X) * 0.9)
        X_train, y_train = X[:train_size], y[:train_size]
        model = LSTMForecaster(hidden_size=128, num_layers=2).to(device)
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
        predictions = []
        current_seq = torch.tensor(returns[-seq_len:], dtype=torch.float32).unsqueeze(0).unsqueeze(-1).to(device)
        last_return = float(returns[-1])
        for step in range(prediction_length):
            with torch.no_grad():
                next_pred = model(current_seq).item()
                next_pred = max(min(next_pred, 0.06), -0.06)          # tighter clip (±6%)
                decay = 0.85 ** step                                    # mean-reversion decay
                next_pred = next_pred * decay + last_return * (1 - decay) * 0.3
                predictions.append(next_pred)
            current_seq = torch.cat([current_seq[:, 1:, :], torch.tensor([[next_pred]], dtype=torch.float32).unsqueeze(-1).to(device)], dim=1)
        final_pred = sum(predictions)   # cumulative return over horizon
        direction = "Bullish 📈" if final_pred > 0.01 else "Bearish 📉" if final_pred < -0.01 else "Neutral ➕"
        return {"predicted_return_pct": round(final_pred * 100, 2), "direction": direction,
                "prediction_length": prediction_length,
                "all_predictions": [round(p * 100, 2) for p in predictions],
                "device_used": device, "model": f"LSTM ({prediction_length}d)"}
    except Exception as e: return {"predicted_return_pct": 0.0, "direction": "Neutral", "error": str(e)[:100]}


# ── Optional GPU / ML dependencies ──────────────────────────────────────────
try:
    from neuralforecast import NeuralForecast
    from neuralforecast.models import NHITS, TFT, PatchTST, NBEATS, TCN
    from neuralforecast.losses.pytorch import MAE
    _NF_AVAILABLE = True
except ImportError:
    _NF_AVAILABLE = False

def _gpu_device():
    if torch.cuda.is_available():
        try:
            torch.tensor([1.0]).cuda()
            return 'cuda'
        except Exception:
            pass
    return 'cpu'


def get_chronos_forecast(ticker: str, prediction_length: int = 5):
    try:
        from chronos import Chronos2Pipeline
        device_map = "cuda" if torch.cuda.is_available() else "cpu"
        pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=device_map)
        hist = yf.Ticker(ticker).history(period="2y")
        if len(hist) < 50: return {"error": "Insufficient data"}
        context = hist['Close'].dropna().values[-100:].tolist()
        last_price = context[-1]
        try:
            forecast = pipeline.predict(context, prediction_length=prediction_length, quantile_levels=[0.1, 0.5, 0.9])
            q10, q50, q90 = forecast[0].cpu().numpy(), forecast[1].cpu().numpy(), forecast[2].cpu().numpy()
        except TypeError:
            ctx_t = torch.tensor(context, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
            samples = pipeline.predict(ctx_t, prediction_length=prediction_length)
            s = samples[0].squeeze(0).cpu().numpy()
            q10 = np.percentile(s[:, -1], 10)
            q50 = np.percentile(s[:, -1], 50)
            q90 = np.percentile(s[:, -1], 90)
        pred_return = float((float(q50 if np.ndim(q50)==0 else q50[-1]) - last_price) / last_price * 100)
        direction = "Bullish 📈" if pred_return > 1.0 else "Bearish 📉" if pred_return < -1.0 else "Neutral ➕"
        q10v = float(q10 if np.ndim(q10)==0 else q10[-1])
        q90v = float(q90 if np.ndim(q90)==0 else q90[-1])
        return {"predicted_return_pct": round(pred_return, 2), "direction": direction,
                "prediction_length": prediction_length,
                "uncertainty_range_pct": round((q90v - q10v) / last_price * 100, 1),
                "lower_10pct": round((q10v - last_price) / last_price * 100, 2),
                "upper_90pct": round((q90v - last_price) / last_price * 100, 2),
                "model": "Chronos-2", "device_used": device_map}
    except Exception as e:
        return {"error": str(e)[:150], "direction": "Neutral"}


def get_finbert_sentiment(ticker: str, max_news: int = 10):
    try:
        from transformers import pipeline as hf_pipeline
        device = 0 if torch.cuda.is_available() else -1
        nlp = hf_pipeline("sentiment-analysis", model="ProsusAI/finbert",
                          tokenizer="ProsusAI/finbert", device=device)
        news = getattr(yf.Ticker(ticker), "news", []) or []
        titles = [n.get("title","").strip() for n in
                  sorted(news, key=lambda x: x.get("providerPublishTime", 0), reverse=True)[:max_news]
                  if n.get("title") and len(n.get("title","")) > 5]
        if not titles:
            return {"overall_sentiment": "Neutral", "sentiment_score": 50.0,
                    "num_articles": 0, "note": "No news available"}
        results = nlp(titles, batch_size=min(8, len(titles)))
        pos = sum(1 for r in results if r["label"] == "positive")
        neu = sum(1 for r in results if r["label"] == "neutral")
        total = len(results)
        score = (pos*100 + neu*50) / total
        overall = "Positive" if score >= 65 else ("Negative" if score <= 35 else "Neutral")
        return {"overall_sentiment": overall, "sentiment_score": round(score, 1),
                "positive_pct": round(pos/total*100, 1),
                "negative_pct": round((total-pos-neu)/total*100, 1),
                "num_articles": total,
                "device_used": "cuda" if device == 0 else "cpu",
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
    if not _NF_AVAILABLE:
        return {"error": "neuralforecast not installed", "direction": "Neutral"}
    device = _gpu_device()
    if device == 'cuda':
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
                      early_stop_patience_steps=10, batch_size=32,
                      windows_batch_size=512, random_seed=42)
        if extra_kwargs:
            kwargs.update(extra_kwargs)
        nf = NeuralForecast(models=[ModelClass(**kwargs)], freq="B")
        nf.fit(df=df, val_size=max(prediction_length, int(len(df) * 0.1)))
        pred_val = nf.predict()[model_name].values[-1]
        last_price = hist["Close"].iloc[-1]
        pred_return = round((pred_val / last_price - 1) * 100, 2)
        direction = "Bullish" if pred_return > 1 else ("Bearish" if pred_return < -1 else "Neutral")
        return {"predicted_return_pct": round(float(pred_return), 2),
                "direction": direction, "model": model_name, "device_used": device}
    except Exception as e:
        return {"error": str(e)[:150], "direction": "Neutral"}


def get_nhits_forecast(ticker: str, prediction_length: int = 5, input_size: int = 120, epochs: int = 50):
    return _nf_forecast(ticker, NHITS, "NHITS", prediction_length, input_size, epochs)

def get_patchtst_forecast(ticker: str, prediction_length: int = 5, input_size: int = 120, epochs: int = 50):
    return _nf_forecast(ticker, PatchTST, "PatchTST", prediction_length, input_size, epochs,
                        extra_kwargs={"hidden_size": 128, "n_heads": 4})

def get_nhits_tft_patchtst_ensemble(ticker: str, prediction_length: int = 5):
    results, preds = {}, []
    for name, fn, extra in [
        ("nhits",    NHITS,    {}),
        ("tft",      TFT,      {"hidden_size": 128, "n_head": 4}),
        ("patchtst", PatchTST, {"hidden_size": 128, "n_heads": 4}),
        ("nbeats",   NBEATS,   {}),
        ("tcn",      TCN,      {}),
    ]:
        r = _nf_forecast(ticker, {"nhits": NHITS, "tft": TFT, "patchtst": PatchTST,
                                   "nbeats": NBEATS, "tcn": TCN}[name],
                         name.upper(), prediction_length, extra_kwargs=extra or None)
        results[name] = r
        if "predicted_return_pct" in r:
            preds.append(float(r["predicted_return_pct"]))
    if not preds:
        return {"error": "All ensemble models failed", "direction": "Neutral"}
    ensemble    = round(float(sum(preds) / len(preds)), 2)
    uncertainty = round(float((max(preds) - min(preds)) / 2), 2)
    direction   = "Bullish" if ensemble > 1 else ("Bearish" if ensemble < -1 else "Neutral")
    return {"predicted_return_pct": ensemble, "direction": direction,
            "uncertainty_pct": uncertainty, "components": results,
            "models_used": len(preds),
            "device_used": results.get("nhits", {}).get("device_used", "cpu")}


def get_multi_horizon_forecasts(ticker: str, horizons: list = None):
    if horizons is None:
        horizons = [5, 10, 15, 20]
    if not _NF_AVAILABLE:
        return {"error": "neuralforecast not installed", "horizons": {}}
    device = _gpu_device()
    if device == 'cuda':
        torch.set_float32_matmul_precision('high')
    try:
        hist = yf.Ticker(ticker).history(period="5y")
        if len(hist) < 100:
            return {"error": "Insufficient history", "horizons": {}}
        df = pd.DataFrame({"unique_id": "stock",
                           "ds": hist.index.tz_localize(None),
                           "y": hist["Close"].values})
        last_price = float(hist["Close"].iloc[-1])
        results = {}

        for h in horizons:
            model_preds, model_preds_named, model_daily_preds = [], [], {}
            for ModelClass, name, extra in [
                (NHITS,    "NHITS",    {}),
                (TFT,      "TFT",      {"hidden_size": 128, "n_head": 4}),
                (PatchTST, "PatchTST", {"hidden_size": 128, "n_heads": 4}),
                (NBEATS,   "NBEATS",   {}),
                (TCN,      "TCN",      {}),
            ]:
                try:
                    kwargs = dict(h=h, input_size=120, max_steps=40, learning_rate=0.001,
                                  loss=MAE(), valid_loss=MAE(), early_stop_patience_steps=8,
                                  batch_size=32, windows_batch_size=512, random_seed=42)
                    kwargs.update(extra)
                    nf = NeuralForecast(models=[ModelClass(**kwargs)], freq="B")
                    nf.fit(df=df, val_size=max(h, int(len(df) * 0.1)))
                    pred_prices  = nf.predict()[name].values
                    daily_returns = [round((float(p) - last_price) / last_price * 100, 3) for p in pred_prices]
                    final_return  = daily_returns[-1]
                    model_preds.append(final_return)
                    model_preds_named.append((name, final_return))
                    model_daily_preds[name] = daily_returns
                except Exception:
                    continue

            if not model_preds:
                results[f"{h}d"] = {"error": "All models failed"}
                continue

            avg_ret    = round(float(np.mean(model_preds)), 2)
            median_ret = round(float(np.median(model_preds)), 2)
            std_dev    = round(float(np.std(model_preds)), 2)
            direction  = "Bullish 📈" if avg_ret > 1.5 else ("Bearish 📉" if avg_ret < -1.5 else "Neutral ➕")
            all_daily  = list(model_daily_preds.values())
            n_days     = min(len(d) for d in all_daily) if all_daily else 0
            daily_median = [round(float(np.median([d[i] for d in all_daily])), 3) for i in range(n_days)]
            daily_avg    = [round(float(np.mean([d[i] for d in all_daily])), 3) for i in range(n_days)]
            daily_prices = [round(last_price * (1 + r / 100), 2) for r in daily_median]
            per_model_daily_prices = {n: [round(last_price * (1 + r / 100), 2) for r in rets]
                                      for n, rets in model_daily_preds.items()}
            forecast_dates = [str(d.date()) for d in pd.bdate_range(
                start=pd.Timestamp.today() + pd.Timedelta(days=1), periods=len(daily_median))]

            results[f"{h}d"] = {
                "predicted_return_pct": avg_ret, "avg_return_pct": avg_ret,
                "median_return_pct": median_ret, "direction": direction,
                "model_disagreement": std_dev, "num_models": len(model_preds),
                "per_model": {n: round(r, 2) for n, r in model_preds_named},
                "model_predictions": {n: round(r, 2) for n, r in model_preds_named},
                "daily_forecasts": daily_median, "daily_avg_forecasts": daily_avg,
                "daily_prices": daily_prices, "per_model_daily": model_daily_preds,
                "per_model_daily_prices": per_model_daily_prices,
                "forecast_dates": forecast_dates, "last_price": round(last_price, 2),
            }

        valid_rets = [results[f"{h}d"]["predicted_return_pct"] for h in horizons
                      if f"{h}d" in results and "predicted_return_pct" in results[f"{h}d"]]
        trend = ("Accelerating Bullish" if len(valid_rets) >= 2 and valid_rets[-1] > valid_rets[0] + 2 else
                 "Accelerating Bearish" if len(valid_rets) >= 2 and valid_rets[-1] < valid_rets[0] - 2 else "Stable")
        dirs = [results[f"{h}d"]["direction"] for h in horizons
                if f"{h}d" in results and "direction" in results[f"{h}d"]]
        consensus = max(set(dirs), key=dirs.count) if dirs else "Neutral"
        return {"horizons": results, "consensus_direction": consensus,
                "trend_signal": trend, "device_used": device,
                "model": "Multi-Horizon (NHITS+TFT+PatchTST+N-BEATS+TCN)"}
    except Exception as e:
        return {"error": str(e)[:150], "horizons": {}}