import pandas as pd
from signals import (get_iv_rank_and_skew, calculate_altman_beneish, get_earnings_surprise,
                     get_rolling_beta, calculate_piotroski_f_score, get_atr_volatility_clustering,
                     get_relative_strength, get_market_regime, get_garch_forecast,
                     get_momentum_and_52w_high, get_quality_accruals_gross_profit,
                     get_amihud_illiquidity, get_share_turnover, get_volume_price_correlation,
                     get_simple_formulaic_alpha, get_obv, get_chaikin_money_flow,
                     get_monte_carlo_risk,
                     get_lstm_forecast, get_chronos_forecast, get_finbert_sentiment,
                     get_nhits_tft_patchtst_ensemble)
from dcf import calculate_dcf
from gpu_utils import gpu_available


def calculate_pillars(data: dict, profile: str = "Balanced"):
    ticker = data['ticker']
    info   = data['info']

    # ── CPU signals ──────────────────────────────────────────────────────────
    iv_signal       = get_iv_rank_and_skew(ticker)
    distress        = calculate_altman_beneish(ticker)
    earnings        = get_earnings_surprise(ticker)
    beta            = get_rolling_beta(ticker)
    dcf_val         = calculate_dcf(data)
    piotroski       = calculate_piotroski_f_score(ticker)
    atr_vol         = get_atr_volatility_clustering(ticker)
    rs              = get_relative_strength(ticker)
    regime          = get_market_regime(ticker)
    garch           = get_garch_forecast(ticker)
    momentum        = get_momentum_and_52w_high(ticker)
    quality         = get_quality_accruals_gross_profit(ticker)
    amihud          = get_amihud_illiquidity(ticker)
    turnover        = get_share_turnover(ticker)
    vol_price       = get_volume_price_correlation(ticker)
    formulaic_alpha = get_simple_formulaic_alpha(ticker)
    obv             = get_obv(ticker)
    cmf             = get_chaikin_money_flow(ticker)
    mc_risk         = get_monte_carlo_risk(ticker)

    # ── GPU signals (with CPU fallback) ──────────────────────────────────────
    gpu = gpu_available()
    print(f"{'🖥️  Running GPU signals (LSTM, Chronos-2, FinBERT, 5-model Ensemble)...' if gpu else '💻 Running ML signals on CPU...'}", flush=True)

    lstm        = get_lstm_forecast(ticker)
    chronos     = get_chronos_forecast(ticker)
    finbert     = get_finbert_sentiment(ticker)
    dl_ensemble = get_nhits_tft_patchtst_ensemble(ticker)

    # ── Pillar scoring ───────────────────────────────────────────────────────
    dcf_upside = dcf_val.get('upside_pct', 0) if dcf_val.get('available') else 0

    regime_bonus   = 8 if regime['regime'] == "Bull" else (-8 if regime['regime'] == "Bear" else 0)
    vol_penalty    = -6 if garch['vol_ratio'] > 1.4 else 0
    quality_boost  = (quality['gross_profitability'] * 0.3) + (10 if quality['high_quality'] else 0)
    liquidity_boost = (turnover.get('turnover', 0) * 0.05) - (amihud.get('amihud', 0) * 5000)
    vol_alpha_boost = ((vol_price['vol_price_corr'] * 15) + (formulaic_alpha['alpha'] * 25)
                       + (cmf['cmf'] * 20) + (obv['obv_change_20d_pct'] * 0.08))
    mom_boost      = ((momentum['momentum_6m'] * 0.15) + (momentum['momentum_12m'] * 0.1)
                      + (8 if momentum['near_52w_high'] else 0))

    # LSTM signal boost to technicals (capped ±8 pts)
    lstm_boost = 0.0
    if 'signal_strength' in lstm and 'direction' in lstm:
        strength = lstm['signal_strength'] / 100
        lstm_boost = strength * (8 if lstm['direction'] == 'Bullish' else -8)

    # DL Ensemble boost to technicals (capped ±10 pts)
    dl_boost = 0.0
    if 'predicted_5d_return_pct' in dl_ensemble:
        dl_pred = dl_ensemble['predicted_5d_return_pct']
        dl_boost = max(-10, min(10, dl_pred * 2))

    # FinBERT sentiment adjustment (replaces earnings-only sentiment)
    finbert_score = finbert.get('sentiment_score', 50.0)
    finbert_adj   = (finbert_score - 50) * 0.3   # -15 to +15 pts

    fundamentals = min(95, max(30,
        (info.get('returnOnEquity', 0) * 50)
        + (info.get('revenueGrowth', 0) * 30)
        + (dcf_upside * 0.2)
        + (piotroski * 2)
        + quality_boost
        + liquidity_boost
    ))

    technicals = min(95, max(30,
        60
        + (iv_signal['ivr'] - 50) * 0.4
        + (beta['alpha'] * 100)
        + (rs['rs_spy'] * 0.3)
        + (5 if atr_vol['vol_clustering'] == "Low" else -10)
        + regime_bonus
        + vol_penalty
        + mom_boost
        + vol_alpha_boost
        + lstm_boost
        + dl_boost
    ))

    valuation = min(95, max(30, 60 + (dcf_upside * 0.3)))

    sentiment = min(95, max(30,
        65
        + (earnings['avg_surprise_pct'] * 1.2)
        + finbert_adj
    ))

    esg_quality = min(95, max(40,
        70 + (10 if distress['risk_level'] == "Safe" else -15) + (piotroski * 2)
    ))

    weights = {
        "Balanced": {"fund": 0.30, "tech": 0.25, "val": 0.25, "sent": 0.10, "esg": 0.10},
        "Growth":   {"fund": 0.35, "tech": 0.30, "val": 0.20, "sent": 0.10, "esg": 0.05},
        "Value":    {"fund": 0.25, "tech": 0.20, "val": 0.35, "sent": 0.10, "esg": 0.10},
        "Momentum": {"fund": 0.20, "tech": 0.35, "val": 0.20, "sent": 0.15, "esg": 0.10},
    }
    w = weights.get(profile, weights["Balanced"])
    overall = (fundamentals * w["fund"] + technicals * w["tech"]
               + valuation * w["val"] + sentiment * w["sent"] + esg_quality * w["esg"])

    return {
        "overall":      round(overall, 1),
        "fundamentals": round(fundamentals, 1),
        "technicals":   round(technicals, 1),
        "valuation":    round(valuation, 1),
        "sentiment":    round(sentiment, 1),
        "esg_quality":  round(esg_quality, 1),
        "signals": {
            "ivr": iv_signal, "distress": distress, "earnings": earnings,
            "beta": beta, "dcf": dcf_val, "piotroski": piotroski,
            "atr_vol": atr_vol, "rs": rs, "regime": regime, "garch": garch,
            "momentum": momentum, "quality": quality, "amihud": amihud,
            "turnover": turnover, "vol_price": vol_price,
            "formulaic_alpha": formulaic_alpha, "obv": obv, "cmf": cmf,
            "mc_risk": mc_risk,
            # GPU signals
            "lstm":        lstm,
            "chronos":     chronos,
            "finbert":     finbert,
            "dl_ensemble": dl_ensemble,
        }
    }
