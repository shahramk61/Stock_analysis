import pandas as pd
from signals import (get_iv_rank_and_skew, calculate_altman_beneish, get_earnings_surprise,
                     get_rolling_beta, calculate_piotroski_f_score, get_atr_volatility_clustering,
                     get_relative_strength, get_market_regime, get_garch_forecast,
                     get_momentum_and_52w_high, get_quality_accruals_gross_profit,
                     get_amihud_illiquidity, get_share_turnover, get_volume_price_correlation,
                     get_simple_formulaic_alpha, get_obv, get_chaikin_money_flow,
                     get_monte_carlo_risk,
                     get_classic_technicals, get_trend_structure, get_adx, normalize_direction,
                     get_lstm_forecast, get_chronos_forecast, get_finbert_sentiment,
                     get_nhits_tft_patchtst_ensemble, get_multi_horizon_forecasts)
from dcf import calculate_dcf
from gpu_utils import gpu_available


def calculate_pillars(data: dict, profile: str = "Balanced", compute_dynamic_weights: bool = False,
                      hist: "pd.DataFrame | None" = None, asof: str | None = None,
                      use_gpu_signals: bool = True, use_forecasts: bool = False,
                      full_horizons: bool = False):
    """Compute pillars and signals. Supports `hist`/`asof` for historical backtesting replay.

    Set use_gpu_signals=False for fast backtests (skips heavy ML).
    use_forecasts defaults False (audit: multi-horizon is research-only / opt-in).
    Set full_horizons=True for 5/10/15/20/50d (default is 5/20/50 for speed).

    Six pillars: Fundamentals, Technicals, Valuation, Sentiment, ESG, Risk.
    """
    ticker = data['ticker']
    info   = data['info']

    kw = {"hist": hist, "asof": asof}

    # ── CPU signals ──────────────────────────────────────────────────────────
    iv_signal       = get_iv_rank_and_skew(ticker, **kw)
    distress        = calculate_altman_beneish(ticker)
    earnings        = get_earnings_surprise(ticker)
    beta            = get_rolling_beta(ticker, **kw)
    dcf_val         = calculate_dcf(data)
    piotroski       = calculate_piotroski_f_score(ticker)
    atr_vol         = get_atr_volatility_clustering(ticker, **kw)
    rs              = get_relative_strength(ticker, **kw)
    regime          = get_market_regime(ticker, **kw)
    garch           = get_garch_forecast(ticker, **kw)
    momentum        = get_momentum_and_52w_high(ticker, **kw)
    quality         = get_quality_accruals_gross_profit(ticker)
    amihud          = get_amihud_illiquidity(ticker, **kw)
    turnover        = get_share_turnover(ticker, **kw)
    vol_price       = get_volume_price_correlation(ticker, **kw)
    formulaic_alpha = get_simple_formulaic_alpha(ticker, **kw)
    obv             = get_obv(ticker, **kw)
    cmf             = get_chaikin_money_flow(ticker, **kw)
    mc_risk         = get_monte_carlo_risk(ticker, **kw)
    classic         = get_classic_technicals(ticker, **kw)
    trend           = get_trend_structure(ticker, **kw)
    adx             = get_adx(ticker, **kw)

    # ── GPU / heavy signals ──────────────────────────────────────────────────
    # Dedupe: one multi_horizon ensemble is enough for pillar boosts (avoid
    # also training standalone LSTM + Chronos + 5-model ensemble every run).
    if use_gpu_signals:
        gpu = gpu_available()
        print(
            f"{'🖥️  Running GPU signals (FinBERT + multi-horizon ensemble)...' if gpu else '💻 Running ML signals on CPU...'}",
            flush=True,
        )
        finbert = get_finbert_sentiment(ticker)
        if use_forecasts:
            multi_h = get_multi_horizon_forecasts(
                ticker,
                compute_dynamic_weights=compute_dynamic_weights,
                full_horizons=full_horizons,
                **{k: v for k, v in kw.items() if v is not None},
            )
            h5 = (multi_h.get("horizons") or {}).get("5d") or {}
            pred = float(h5.get("predicted_return_pct") or h5.get("median_return_pct") or 0.0)
            direction = normalize_direction(h5.get("direction", multi_h.get("consensus_direction", "Neutral")))
            # Derive lightweight boost sources from multi_h (no extra training)
            lstm = {
                "predicted_return_pct": pred,
                "direction": direction,
                "signal_strength": min(100.0, abs(pred) * 10.0),
                "source": "multi_horizon_5d",
            }
            chronos = {
                "predicted_return_pct": pred,
                "direction": direction,
                "source": "multi_horizon_5d",
            }
            dl_ensemble = {
                "predicted_return_pct": pred,
                "direction": direction,
                "source": "multi_horizon_5d",
                "uncertainty_pct": h5.get("model_disagreement"),
            }
        else:
            lstm = {"predicted_return_pct": 0.0, "direction": "Neutral", "signal_strength": 0}
            chronos = {"predicted_return_pct": 0.0, "direction": "Neutral"}
            dl_ensemble = {"predicted_return_pct": 0.0}
            multi_h = {"horizons": {}, "consensus_direction": "Neutral", "trend_signal": "Stable"}
    else:
        finbert = {"overall_sentiment": "Neutral", "sentiment_score": 50.0}
        lstm = {"predicted_return_pct": 0.0, "direction": "Neutral", "signal_strength": 0}
        chronos = {"predicted_return_pct": 0.0, "direction": "Neutral"}
        dl_ensemble = {"predicted_return_pct": 0.0}
        multi_h = {"horizons": {}, "consensus_direction": "Neutral", "trend_signal": "Stable"}

    # ── Pillar scoring ───────────────────────────────────────────────────────
    dcf_upside = dcf_val.get('upside_pct', 0) if dcf_val.get('available') else 0

    regime_bonus   = 8 if regime.get('regime') == "Bull" else (-8 if regime.get('regime') == "Bear" else 0)
    vol_penalty    = -6 if garch.get('vol_ratio', 1) > 1.4 else 0
    quality_boost  = (quality.get('gross_profitability', 0) * 0.3) + (10 if quality.get('high_quality') else 0)
    liquidity_boost = (turnover.get('turnover', 0) * 0.05) - (amihud.get('amihud', 0) * 5000)
    vol_alpha_boost = ((vol_price.get('vol_price_corr', 0) * 15) + (formulaic_alpha.get('alpha', 0) * 25)
                       + (cmf.get('cmf', 0) * 20) + (obv.get('obv_change_20d_pct', 0) * 0.08))
    mom_boost      = ((momentum.get('momentum_6m', 0) * 0.15) + (momentum.get('momentum_12m', 0) * 0.1)
                      + (8 if momentum.get('near_52w_high') else 0))

    # Classic + trend pack boosts (capped)
    rsi = classic.get("rsi", 50)
    classic_boost = 0.0
    if rsi <= 30:
        classic_boost += 4   # oversold bounce potential
    elif rsi >= 70:
        classic_boost -= 4
    macd_cross = classic.get("macd_cross", "Neutral")
    if macd_cross in ("Bullish", "BullishCross"):
        classic_boost += 3
    elif macd_cross in ("Bearish", "BearishCross"):
        classic_boost -= 3

    trend_boost = 0.0
    if trend.get("stack") == "Bullish":
        trend_boost += 5
    elif trend.get("stack") == "Bearish":
        trend_boost -= 5
    if trend.get("golden_cross"):
        trend_boost += 3
    if trend.get("death_cross"):
        trend_boost -= 3
    adx_val = adx.get("adx", 0)
    if adx_val >= 25 and adx.get("plus_di", 0) > adx.get("minus_di", 0):
        trend_boost += 2
    elif adx_val >= 25 and adx.get("minus_di", 0) > adx.get("plus_di", 0):
        trend_boost -= 2

    # Forecast boosts from multi_h-derived stubs
    lstm_boost = 0.0
    if 'signal_strength' in lstm and 'direction' in lstm:
        strength = float(lstm.get('signal_strength') or 0) / 100
        d = normalize_direction(lstm.get('direction'))
        lstm_boost = strength * (8 if d == 'Bullish' else (-8 if d == 'Bearish' else 0))

    dl_boost = 0.0
    if 'predicted_return_pct' in dl_ensemble:
        dl_pred = float(dl_ensemble.get('predicted_return_pct') or 0)
        dl_boost = max(-10, min(10, dl_pred * 2))

    finbert_score = finbert.get('sentiment_score', 50.0)
    finbert_adj   = (finbert_score - 50) * 0.3

    fundamentals = min(95, max(30,
        (info.get('returnOnEquity', 0) or 0) * 50
        + (info.get('revenueGrowth', 0) or 0) * 30
        + (dcf_upside * 0.2)
        + (piotroski * 2 if isinstance(piotroski, (int, float)) else 0)
        + quality_boost
        + liquidity_boost
    ))

    technicals = min(95, max(30,
        60
        + (iv_signal.get('ivr', 50) - 50) * 0.4
        + (beta.get('alpha', 0) * 100)
        + (rs.get('rs_spy', 0) * 0.3)
        + (5 if atr_vol.get('vol_clustering') == "Low" else -10)
        + regime_bonus
        + vol_penalty
        + mom_boost
        + vol_alpha_boost
        + classic_boost
        + trend_boost
        + lstm_boost
        + dl_boost
    ))

    valuation = min(95, max(30, 60 + (dcf_upside * 0.3)))

    sentiment = min(95, max(30,
        65
        + (earnings.get('avg_surprise_pct', 0) * 1.2)
        + finbert_adj
    ))

    esg_quality = min(95, max(40,
        70 + (10 if distress.get('risk_level') == "Safe" else -15)
        + (piotroski * 2 if isinstance(piotroski, (int, float)) else 0)
    ))

    # Risk pillar (higher = safer / more favorable risk profile)
    risk_score = 70.0
    var95 = float(mc_risk.get("var_95") or 20)
    if var95 > 30:
        risk_score -= 20
    elif var95 > 20:
        risk_score -= 10
    elif var95 < 12:
        risk_score += 5
    if garch.get("vol_ratio", 1) > 1.4:
        risk_score -= 8
    if atr_vol.get("vol_clustering") == "High":
        risk_score -= 8
    if distress.get("risk_level") == "Distress":
        risk_score -= 15
    elif distress.get("risk_level") == "Grey":
        risk_score -= 5
    if regime.get("regime") == "Bear":
        risk_score -= 10
    elif regime.get("regime") == "Bull":
        risk_score += 4
    risk_score = min(95, max(20, risk_score))

    # Profile weights (include Risk; match README intent)
    weights = {
        "Balanced": {"fund": 0.25, "tech": 0.20, "val": 0.20, "sent": 0.10, "esg": 0.10, "risk": 0.15},
        "Growth":   {"fund": 0.30, "tech": 0.25, "val": 0.15, "sent": 0.10, "esg": 0.05, "risk": 0.15},
        "Value":    {"fund": 0.20, "tech": 0.15, "val": 0.30, "sent": 0.10, "esg": 0.10, "risk": 0.15},
        "Momentum": {"fund": 0.15, "tech": 0.30, "val": 0.15, "sent": 0.15, "esg": 0.10, "risk": 0.15},
    }
    w = weights.get(profile, weights["Balanced"])
    overall = (
        fundamentals * w["fund"]
        + technicals * w["tech"]
        + valuation * w["val"]
        + sentiment * w["sent"]
        + esg_quality * w["esg"]
        + risk_score * w["risk"]
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
            "ivr": iv_signal, "distress": distress, "earnings": earnings,
            "beta": beta, "dcf": dcf_val, "piotroski": piotroski,
            "atr_vol": atr_vol, "rs": rs, "regime": regime, "garch": garch,
            "momentum": momentum, "quality": quality, "amihud": amihud,
            "turnover": turnover, "vol_price": vol_price,
            "formulaic_alpha": formulaic_alpha, "obv": obv, "cmf": cmf,
            "mc_risk":   mc_risk,
            "classic":   classic,
            "trend":     trend,
            "adx":       adx,
            "multi_h":   multi_h,
            "lstm":        lstm,
            "chronos":     chronos,
            "finbert":     finbert,
            "dl_ensemble": dl_ensemble,
        }
    }
