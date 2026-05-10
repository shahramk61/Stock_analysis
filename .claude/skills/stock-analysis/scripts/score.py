import pandas as pd
from signals import get_iv_rank_and_skew, calculate_altman_beneish, get_earnings_surprise, get_rolling_beta, calculate_piotroski_f_score, get_atr_volatility_clustering, get_relative_strength, get_market_regime, get_garch_forecast, get_momentum_and_52w_high, get_quality_accruals_gross_profit
from dcf import calculate_dcf

def calculate_pillars(data: dict, profile: str = "Balanced"):
    ticker = data['ticker']
    info = data['info']
    current_price = data['current_price']
    
    iv_signal = get_iv_rank_and_skew(ticker)
    distress = calculate_altman_beneish(ticker)
    earnings = get_earnings_surprise(ticker)
    beta = get_rolling_beta(ticker)
    dcf_val = calculate_dcf(data)
    piotroski = calculate_piotroski_f_score(ticker)
    atr_vol = get_atr_volatility_clustering(ticker)
    rs = get_relative_strength(ticker)
    regime = get_market_regime(ticker)
    garch = get_garch_forecast(ticker)
    momentum = get_momentum_and_52w_high(ticker)
    quality = get_quality_accruals_gross_profit(ticker)
    
    dcf_upside = dcf_val.get('upside_pct', 0) if dcf_val.get('available') else 0

    # Regime and vol adjustments
    regime_bonus = 8 if regime['regime'] == "Bull" else -8 if regime['regime'] == "Bear" else 0
    vol_penalty = -6 if garch['vol_ratio'] > 1.4 else 0

    # Quality boost (Novy-Marx Gross Profit + low accruals)
    quality_boost = (quality['gross_profitability'] * 0.3) + (10 if quality['high_quality'] else 0)

    fundamentals = min(95, max(30, (info.get('returnOnEquity', 0) * 50) + (info.get('revenueGrowth', 0) * 30) + (dcf_upside * 0.2) + (piotroski * 2) + quality_boost))

    # Momentum boost
    mom_boost = (momentum['momentum_6m'] * 0.15) + (momentum['momentum_12m'] * 0.1) + (8 if momentum['near_52w_high'] else 0)

    technicals = min(95, max(30, 60 + (iv_signal['ivr'] - 50) * 0.4 + (beta['alpha'] * 100) + (rs['rs_spy'] * 0.3) + (5 if atr_vol['vol_clustering'] == "Low" else -10) + regime_bonus + vol_penalty + mom_boost))

    valuation = min(95, max(30, 60 + (dcf_upside * 0.3)))
    
    sentiment = min(95, max(30, 65 + (earnings['avg_surprise_pct'] * 1.2)))
    
    esg_quality = min(95, max(40, 70 + (10 if distress['risk_level'] == "Safe" else -15) + (piotroski * 2)))
    
    weights = {
        "Balanced": {"fund":0.30, "tech":0.25, "val":0.25, "sent":0.10, "esg":0.10},
        "Growth": {"fund":0.35, "tech":0.30, "val":0.20, "sent":0.10, "esg":0.05},
        "Value": {"fund":0.25, "tech":0.20, "val":0.35, "sent":0.10, "esg":0.10},
        "Momentum": {"fund":0.20, "tech":0.35, "val":0.20, "sent":0.15, "esg":0.10},
    }
    
    w = weights.get(profile, weights["Balanced"])
    
    overall = (fundamentals * w["fund"] + technicals * w["tech"] + valuation * w["val"] + sentiment * w["sent"] + esg_quality * w["esg"])
    
    return {
        "overall": round(overall, 1),
        "fundamentals": round(fundamentals, 1),
        "technicals": round(technicals, 1),
        "valuation": round(valuation, 1),
        "sentiment": round(sentiment, 1),
        "esg_quality": round(esg_quality, 1),
        "signals": {
            "ivr": iv_signal,
            "distress": distress,
            "earnings": earnings,
            "beta": beta,
            "dcf": dcf_val,
            "piotroski": piotroski,
            "atr_vol": atr_vol,
            "rs": rs,
            "regime": regime,
            "garch": garch,
            "momentum": momentum,
            "quality": quality
        }
    }
