import yfinance as yf
import pandas as pd
import numpy as np
from .utils import _gpu_device
from .ml_forecast import get_lstm_forecast, get_chronos_forecast

try:
    import torch
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


def get_nhits_forecast(ticker, prediction_length=5): return {"error": "Coming soon"}
def get_tft_forecast(ticker, prediction_length=5): return {"error": "Coming soon"}
def get_patchtst_forecast(ticker, prediction_length=5): return {"error": "Coming soon"}
def get_nbeats_forecast(ticker, prediction_length=5): return {"error": "Coming soon"}
def get_tcn_forecast(ticker, prediction_length=5): return {"error": "Coming soon"}
def get_nhits_tft_patchtst_ensemble(ticker, prediction_length=5): return {"error": "Coming soon"}


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


def _compute_dynamic_weights(ticker: str, val_h: int = 10):
    """Out-of-sample backtest to derive per-model weights (1/MAE normalized)."""
    if not (_NF_AVAILABLE and _TORCH_AVAILABLE):
        return None
    try:
        hist = yf.Ticker(ticker).history(period="5y")
        if len(hist) < val_h + 200:
            return None
        # Simplified: return None (placeholder for full backtest logic)
        return None
    except Exception:
        return None


def get_multi_horizon_forecasts(ticker: str, horizons: list = None, compute_dynamic_weights: bool = False):
    """
    Multi-horizon ensemble forecast (5d/10d/15d/20d/50d) using LSTM + Chronos-2
    (NeuralForecast models are stubs until fully implemented).
    """
    if horizons is None:
        horizons = [5, 10, 15, 20, 50]

    device = _gpu_device()
    if _TORCH_AVAILABLE and device == 'cuda':
        torch.set_float32_matmul_precision('high')

    try:
        hist = yf.Ticker(ticker).history(period="5y")
        if len(hist) < 100:
            return {"error": "Insufficient history", "horizons": {}}

        last_price = float(hist["Close"].iloc[-1])
        results = {}

        dynamic_weights_info = _compute_dynamic_weights(ticker, val_h=10) if compute_dynamic_weights else None

        for h in horizons:
            model_preds = []
            model_preds_named = []
            model_daily_preds = {}

            # LSTM
            try:
                lstm_r = get_lstm_forecast(ticker, prediction_length=h)
                if lstm_r and "all_predictions" in lstm_r and "error" not in lstm_r:
                    lstm_inc = lstm_r["all_predictions"]
                    lstm_cum, s = [], 0.0
                    for v in lstm_inc:
                        s += float(v)
                        lstm_cum.append(round(s, 3))
                    if lstm_cum:
                        model_preds.append(lstm_cum[-1])
                        model_preds_named.append(("LSTM", lstm_cum[-1]))
                        model_daily_preds["LSTM"] = lstm_cum
            except Exception:
                pass

            # Chronos-2
            try:
                ch_r = get_chronos_forecast(ticker, prediction_length=h)
                if ch_r and "all_predictions" in ch_r and "error" not in ch_r:
                    ch_cum = list(ch_r["all_predictions"])
                    if ch_cum:
                        model_preds.append(ch_cum[-1])
                        model_preds_named.append(("Chronos", ch_cum[-1]))
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
            wm_dynamic = None
            if dynamic_weights_info and dynamic_weights_info.get("weights"):
                wm_dynamic = _weighted_mean(model_preds_named, dynamic_weights_info["weights"])
            wm_dynamic_rounded = round(wm_dynamic, 2) if wm_dynamic is not None else None
            direction = ("Bullish" if avg_ret > 1.5 else "Bearish" if avg_ret < -1.5 else "Neutral")

            all_daily = list(model_daily_preds.values())
            n_days = min(len(d) for d in all_daily) if all_daily else 0
            daily_median = [round(float(np.median([d[i] for d in all_daily])), 3) for i in range(n_days)]
            daily_avg    = [round(float(np.mean([d[i] for d in all_daily])), 3) for i in range(n_days)]

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
                "weighted_dynamic_pct":    wm_dynamic_rounded,
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

        trend = ("Accelerating Bullish" if len(valid_rets) >= 2 and valid_rets[-1] > valid_rets[0] + 2 else
                 "Accelerating Bearish" if len(valid_rets) >= 2 and valid_rets[-1] < valid_rets[0] - 2 else
                 "Stable")

        dirs = [results[f"{h}d"]["direction"] for h in horizons
                if f"{h}d" in results and "direction" in results[f"{h}d"]]
        consensus = max(set(dirs), key=dirs.count) if dirs else "Neutral"

        return {"horizons": results, "consensus_direction": consensus,
                "trend_signal": trend, "device_used": device,
                "model": "Multi-Horizon (LSTM+Chronos)",
                "static_weights": STATIC_MODEL_WEIGHTS,
                "dynamic_weights_info": dynamic_weights_info,
                "ensemble_methods": ["median", "avg", "weighted_static",
                                     "weighted_dynamic" if dynamic_weights_info else None]}
    except Exception as e:
        return {"error": str(e)[:150], "horizons": {}}
