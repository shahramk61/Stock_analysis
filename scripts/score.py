import pandas as pd
from signals import (
    get_iv_rank_and_skew,
    calculate_altman_beneish,
    get_earnings_surprise,
    get_rolling_beta,
    get_monte_carlo_risk,
    get_lstm_forecast,
    get_chronos_forecast,
    get_nhits_forecast,
    get_patchtst_forecast,
    get_nhits_tft_patchtst_ensemble,
    get_finbert_sentiment,
    get_multi_horizon_forecasts,
)
from dcf import calculate_dcf

def calculate_pillars(data: dict, profile: str = "Balanced"):
    ticker = data['ticker']
    info   = data['info']

    iv_signal        = get_iv_rank_and_skew(ticker)
    distress         = calculate_altman_beneish(ticker)
    earnings         = get_earnings_surprise(ticker)
    beta             = get_rolling_beta(ticker)
    dcf_val          = calculate_dcf(data)
    risk             = get_monte_carlo_risk(ticker)
    lstm_forecast    = get_lstm_forecast(ticker)
    chronos_forecast = get_chronos_forecast(ticker)
    nhits_forecast   = get_nhits_forecast(ticker)
    patchtst_forecast = get_patchtst_forecast(ticker)
    ensemble_forecast = get_nhits_tft_patchtst_ensemble(ticker)
    sentiment_signal  = get_finbert_sentiment(ticker)
    multi_horizon     = get_multi_horizon_forecasts(ticker)

    dcf_upside = dcf_val.get('upside_pct', 0) if dcf_val.get('available') else 0

    fundamentals = min(95, max(30,
        (info.get('returnOnEquity', 0) * 50)
        + (info.get('revenueGrowth', 0) * 30)
        + (dcf_upside * 0.2)
    ))

    technicals = min(95, max(30, 60 + (iv_signal['ivr'] - 50) * 0.4 + (beta['alpha'] * 100)))
    lstm_boost     = lstm_forecast.get('predicted_return_pct', 0) * 0.6
    chronos_boost  = chronos_forecast.get('predicted_return_pct', 0) * 0.3
    ensemble_boost = ensemble_forecast.get('predicted_return_pct', 0) * 0.3
    technicals = min(95, max(30, technicals + lstm_boost + chronos_boost + ensemble_boost))

    valuation  = min(95, max(30, 60 + (dcf_upside * 0.3)))
    sentiment  = min(95, max(30, sentiment_signal.get('sentiment_score', 50.0)))
    esg_quality = min(95, max(40, 70 + (10 if distress['risk_level'] == "Safe" else -15)))
    risk_score  = min(95, max(30, 90 - risk['var_95'] * 1.5 - (risk['cvar_95'] - risk['var_95']) * 0.8))

    weights = {
        "Balanced": {"fund":0.25, "tech":0.20, "val":0.20, "sent":0.10, "esg":0.10, "risk":0.15},
        "Growth":   {"fund":0.30, "tech":0.25, "val":0.15, "sent":0.10, "esg":0.05, "risk":0.15},
        "Value":    {"fund":0.20, "tech":0.15, "val":0.30, "sent":0.10, "esg":0.10, "risk":0.15},
        "Momentum": {"fund":0.15, "tech":0.30, "val":0.15, "sent":0.15, "esg":0.10, "risk":0.15},
    }
    w = weights.get(profile, weights["Balanced"])
    overall = (
        fundamentals * w["fund"] + technicals * w["tech"] +
        valuation * w["val"]    + sentiment  * w["sent"] +
        esg_quality * w["esg"] + risk_score  * w["risk"]
    )

    return {
        "overall":      round(overall, 1),
        "fundamentals": round(fundamentals, 1),
        "technicals":   round(technicals, 1),
        "valuation":    round(valuation, 1),
        "sentiment":    round(sentiment, 1),
        "esg_quality":  round(esg_quality, 1),
        "risk":         round(risk_score, 1),
        "signals": {
            "ivr":                    iv_signal,
            "distress":               distress,
            "earnings":               earnings,
            "beta":                   beta,
            "dcf":                    dcf_val,
            "mc_risk":                risk,
            "lstm_forecast":          lstm_forecast,
            "chronos_forecast":       chronos_forecast,
            "nhits_forecast":         nhits_forecast,
            "patchtst_forecast":      patchtst_forecast,
            "ensemble_forecast":      ensemble_forecast,
            "finbert_sentiment":      sentiment_signal,
            "multi_horizon_forecasts": multi_horizon,
        }
    }
