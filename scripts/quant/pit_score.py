"""
Point-in-time (PIT) score computation for Quant measurement.

Computes pillar scores using ONLY asof-sliced OHLCV data.
Does NOT fetch live yfinance fundamentals unless a PIT fundamental store exists.
Returns structured result with availability ledger.
"""

import pandas as pd
from datetime import datetime
from typing import Any, Dict, Optional

# Import only asof-safe signals from stock_signals
from scripts.stock_signals import (
    get_iv_rank_and_skew,
    get_rolling_beta,
    get_atr_volatility_clustering,
    get_relative_strength,
    get_market_regime,
    get_garch_forecast,
    get_momentum_and_52w_high,
    get_amihud_illiquidity,
    get_volume_price_correlation,
    get_simple_formulaic_alpha,
    get_obv,
    get_chaikin_money_flow,
    get_monte_carlo_risk,
    get_classic_technicals,
    get_trend_structure,
    get_adx,
    normalize_direction,
)


def compute_pit_score(
    ticker: str,
    asof: str | datetime,
    hist: Optional[pd.DataFrame] = None,
    profile: str = "Balanced",
    use_forecasts: bool = False,
) -> Dict[str, Any]:
    """
    Compute point-in-time score at `asof` date using only data available at that time.

    Args:
        ticker: Stock ticker symbol
        asof: As-of date for the score (YYYY-MM-DD or datetime)
        hist: Pre-loaded OHLCV history (must be sliced to <= asof)
        profile: Scoring profile (Balanced/Growth/Value/Momentum)
        use_forecasts: Whether to enable forecast signals (default False)

    Returns:
        Dictionary with:
        - pillar_scores: Dict of computed pillar scores
        - overall_score: Weighted overall score
        - availability: Dict tracking which fields were computed/unavailable/leaked
        - signals: Dict of individual signal values
        - asof: As-of date used
        - ticker: Ticker symbol
    """
    if isinstance(asof, str):
        asof_ts = pd.Timestamp(asof)
    else:
        asof_ts = pd.Timestamp(asof)

    asof_str = str(asof_ts.date())

    # Ensure hist is properly sliced to asof
    if hist is not None:
        if not isinstance(hist.index, pd.DatetimeIndex):
            hist.index = pd.to_datetime(hist.index)
        hist = hist.loc[: asof_ts].copy()
        if hist.empty:
            return {
                "error": f"No data available for {ticker} at {asof_str}",
                "ticker": ticker,
                "asof": asof_str,
            }
    else:
        # If no hist provided, we cannot compute anything safely
        return {
            "error": f"No history provided for {ticker}. PIT scorer requires pre-loaded hist.",
            "ticker": ticker,
            "asof": asof_str,
        }

    # Availability ledger: tracks each field as computed | unavailable | leaked
    availability = {}

    # Signal keyword args
    kw = {"hist": hist, "asof": asof_str}

    # ── PRICE-BASED SIGNALS (asof-safe) ──────────────────────────────────────
    signals = {}

    try:
        signals["ivr"] = get_iv_rank_and_skew(ticker, **kw)
        availability["ivr"] = "computed"
    except Exception:
        signals["ivr"] = {"ivr": 50, "skew": 0.0}
        availability["ivr"] = "unavailable"

    try:
        signals["beta"] = get_rolling_beta(ticker, **kw)
        availability["beta"] = "computed"
    except Exception:
        signals["beta"] = {"beta": 1.0, "alpha": 0.0}
        availability["beta"] = "unavailable"

    try:
        signals["atr_vol"] = get_atr_volatility_clustering(ticker, **kw)
        availability["atr_vol"] = "computed"
    except Exception:
        signals["atr_vol"] = {"vol_clustering": "Normal", "risk_level": "Normal"}
        availability["atr_vol"] = "unavailable"

    try:
        signals["rs"] = get_relative_strength(ticker, **kw)
        availability["rs"] = "computed"
    except Exception:
        signals["rs"] = {"rs_spy": 0, "rs_sector": 0}
        availability["rs"] = "unavailable"

    try:
        signals["regime"] = get_market_regime(ticker, **kw)
        availability["regime"] = "computed"
    except Exception:
        signals["regime"] = {"regime": "Neutral"}
        availability["regime"] = "unavailable"

    try:
        signals["garch"] = get_garch_forecast(ticker, **kw)
        availability["garch"] = "computed"
    except Exception:
        signals["garch"] = {"vol_ratio": 1.0}
        availability["garch"] = "unavailable"

    try:
        signals["momentum"] = get_momentum_and_52w_high(ticker, **kw)
        availability["momentum"] = "computed"
    except Exception:
        signals["momentum"] = {"momentum_6m": 0, "momentum_12m": 0, "near_52w_high": False}
        availability["momentum"] = "unavailable"

    try:
        signals["amihud"] = get_amihud_illiquidity(ticker, **kw)
        availability["amihud"] = "computed"
    except Exception:
        signals["amihud"] = {"amihud": 0.0}
        availability["amihud"] = "unavailable"

    try:
        signals["vol_price"] = get_volume_price_correlation(ticker, **kw)
        availability["vol_price"] = "computed"
    except Exception:
        signals["vol_price"] = {"vol_price_corr": 0.0}
        availability["vol_price"] = "unavailable"

    try:
        signals["formulaic_alpha"] = get_simple_formulaic_alpha(ticker, **kw)
        availability["formulaic_alpha"] = "computed"
    except Exception:
        signals["formulaic_alpha"] = {"alpha": 0.0}
        availability["formulaic_alpha"] = "unavailable"

    try:
        signals["obv"] = get_obv(ticker, **kw)
        availability["obv"] = "computed"
    except Exception:
        signals["obv"] = {"obv_change_20d_pct": 0.0}
        availability["obv"] = "unavailable"

    try:
        signals["cmf"] = get_chaikin_money_flow(ticker, **kw)
        availability["cmf"] = "computed"
    except Exception:
        signals["cmf"] = {"cmf": 0.0}
        availability["cmf"] = "unavailable"

    try:
        signals["mc_risk"] = get_monte_carlo_risk(ticker, **kw)
        availability["mc_risk"] = "computed"
    except Exception:
        signals["mc_risk"] = {"var_95": 20.0}
        availability["mc_risk"] = "unavailable"

    try:
        signals["classic"] = get_classic_technicals(ticker, **kw)
        availability["classic"] = "computed"
    except Exception:
        signals["classic"] = {"rsi": 50.0, "macd_cross": "Neutral"}
        availability["classic"] = "unavailable"

    try:
        signals["trend"] = get_trend_structure(ticker, **kw)
        availability["trend"] = "computed"
    except Exception:
        signals["trend"] = {"stack": "Unknown", "golden_cross": False, "death_cross": False}
        availability["trend"] = "unavailable"

    try:
        signals["adx"] = get_adx(ticker, **kw)
        availability["adx"] = "computed"
    except Exception:
        signals["adx"] = {"adx": 0.0, "trend_strength": "Unknown"}
        availability["adx"] = "unavailable"

    # ── FUNDAMENTAL SIGNALS (NOT AVAILABLE in PIT v1 — withheld) ─────────────
    # These require a point-in-time fundamental store which doesn't exist yet.
    # Mark as unavailable rather than fetching live yfinance.

    for field in [
        "distress",
        "earnings",
        "piotroski",
        "quality",
        "dcf",
        "finbert",
        "turnover",
    ]:
        signals[field] = None
        availability[field] = "unavailable (no PIT fundamental store)"

    # ── FORECAST SIGNALS (opt-in only) ────────────────────────────────────────
    if use_forecasts:
        # Forecasts are research-only; default off
        # If enabled, they would be computed here with hist/asof
        for field in ["lstm", "chronos", "multi_h", "dl_ensemble"]:
            signals[field] = None
            availability[field] = "unavailable (forecasts disabled)"
    else:
        for field in ["lstm", "chronos", "multi_h", "dl_ensemble"]:
            signals[field] = None
            availability[field] = "disabled (use_forecasts=False)"

    # ── PILLAR SCORING (using only computed signals) ─────────────────────────
    # Compute pillars from available signals only. Missing fundamentals will
    # reduce scores to baseline levels.

    regime_bonus = (
        8
        if signals["regime"].get("regime") == "Bull"
        else (-8 if signals["regime"].get("regime") == "Bear" else 0)
    )
    vol_penalty = -6 if signals["garch"].get("vol_ratio", 1) > 1.4 else 0
    liquidity_boost = -(signals["amihud"].get("amihud", 0) * 5000)
    vol_alpha_boost = (
        (signals["vol_price"].get("vol_price_corr", 0) * 15)
        + (signals["formulaic_alpha"].get("alpha", 0) * 25)
        + (signals["cmf"].get("cmf", 0) * 20)
        + (signals["obv"].get("obv_change_20d_pct", 0) * 0.08)
    )
    mom_boost = (
        (signals["momentum"].get("momentum_6m", 0) * 0.15)
        + (signals["momentum"].get("momentum_12m", 0) * 0.1)
        + (8 if signals["momentum"].get("near_52w_high") else 0)
    )

    # Classic + trend boosts
    rsi = signals["classic"].get("rsi", 50)
    classic_boost = 0.0
    if rsi <= 30:
        classic_boost += 4
    elif rsi >= 70:
        classic_boost -= 4
    macd_cross = signals["classic"].get("macd_cross", "Neutral")
    if macd_cross in ("Bullish", "BullishCross"):
        classic_boost += 3
    elif macd_cross in ("Bearish", "BearishCross"):
        classic_boost -= 3

    trend_boost = 0.0
    if signals["trend"].get("stack") == "Bullish":
        trend_boost += 5
    elif signals["trend"].get("stack") == "Bearish":
        trend_boost -= 5
    if signals["trend"].get("golden_cross"):
        trend_boost += 3
    if signals["trend"].get("death_cross"):
        trend_boost -= 3
    adx_val = signals["adx"].get("adx", 0)
    if adx_val >= 25 and signals["adx"].get("plus_di", 0) > signals["adx"].get("minus_di", 0):
        trend_boost += 2
    elif adx_val >= 25 and signals["adx"].get("minus_di", 0) > signals["adx"].get("plus_di", 0):
        trend_boost -= 2

    # Fundamentals pillar: baseline 60 (no fundamental data available)
    fundamentals = 60.0

    # Technicals pillar: computed from price signals
    technicals = min(
        95,
        max(
            30,
            60
            + (signals["ivr"].get("ivr", 50) - 50) * 0.4
            + (signals["beta"].get("alpha", 0) * 100)
            + (signals["rs"].get("rs_spy", 0) * 0.3)
            + (5 if signals["atr_vol"].get("vol_clustering") == "Low" else -10)
            + regime_bonus
            + vol_penalty
            + mom_boost
            + vol_alpha_boost
            + classic_boost
            + trend_boost,
        ),
    )

    # Valuation pillar: baseline 60 (no DCF available)
    valuation = 60.0

    # Sentiment pillar: baseline 65 (no earnings/finbert available)
    sentiment = 65.0

    # ESG/Quality pillar: baseline 70 (no distress/piotroski available)
    esg_quality = 70.0

    # Risk pillar: computed from monte carlo + vol signals
    risk_score = 70.0
    var95 = float(signals["mc_risk"].get("var_95") or 20)
    if var95 > 30:
        risk_score -= 20
    elif var95 > 20:
        risk_score -= 10
    elif var95 < 12:
        risk_score += 5
    if signals["garch"].get("vol_ratio", 1) > 1.4:
        risk_score -= 8
    if signals["atr_vol"].get("vol_clustering") == "High":
        risk_score -= 8
    if signals["regime"].get("regime") == "Bear":
        risk_score -= 10
    elif signals["regime"].get("regime") == "Bull":
        risk_score += 4
    risk_score = min(95, max(20, risk_score))

    # Profile weights
    weights = {
        "Balanced": {
            "fund": 0.25,
            "tech": 0.20,
            "val": 0.20,
            "sent": 0.10,
            "esg": 0.10,
            "risk": 0.15,
        },
        "Growth": {
            "fund": 0.30,
            "tech": 0.25,
            "val": 0.15,
            "sent": 0.10,
            "esg": 0.05,
            "risk": 0.15,
        },
        "Value": {
            "fund": 0.20,
            "tech": 0.15,
            "val": 0.30,
            "sent": 0.10,
            "esg": 0.10,
            "risk": 0.15,
        },
        "Momentum": {
            "fund": 0.15,
            "tech": 0.30,
            "val": 0.15,
            "sent": 0.15,
            "esg": 0.10,
            "risk": 0.15,
        },
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
        "ticker": ticker,
        "asof": asof_str,
        "profile": profile,
        "overall_score": round(overall, 1),
        "pillar_scores": {
            "fundamentals": round(fundamentals, 1),
            "technicals": round(technicals, 1),
            "valuation": round(valuation, 1),
            "sentiment": round(sentiment, 1),
            "esg_quality": round(esg_quality, 1),
            "risk": round(risk_score, 1),
        },
        "availability": availability,
        "signals": signals,
        "use_forecasts": use_forecasts,
    }
