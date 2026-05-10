import pandas as pd
from signals import get_iv_rank_and_skew, calculate_altman_beneish, get_earnings_surprise, get_rolling_beta
from dcf import calculate_dcf

def calculate_pillars(data: dict, profile: str = "Balanced"):
    ticker = data['ticker']
    info = data['info']
    current_price = data['current_price']
    
    iv_signal = get_iv_rank_and_skew(ticker)
    distress = calculate_altman_beneish(ticker)
    earnings = get_earnings_surprise(ticker)
    beta = get_rolling_beta(ticker)
    dcf_val = calculate_dcf(ticker, current_price)
    
    fundamentals = min(95, max(30, (info.get('returnOnEquity', 0) * 50) + (info.get('revenueGrowth', 0) * 30) + (dcf_val.get('upside', 0) * 20)))
    
    technicals = min(95, max(30, 60 + (iv_signal['ivr'] - 50) * 0.4 + (beta['alpha'] * 100)))
    
    valuation = min(95, max(30, (dcf_val.get('fair_value_score', 70)) + (100 if dcf_val.get('upside', 0) > 20 else 40)))
    
    sentiment = min(95, max(30, 65 + (earnings['avg_surprise_pct'] * 1.2)))
    
    esg_quality = min(95, max(40, 70 + (10 if distress['risk_level'] == "Safe" else -15)))
    
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
            "dcf": dcf_val
        }
    }