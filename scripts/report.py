from tabulate import tabulate
import json
from datetime import datetime

def generate_report(data, scores, mc_result, profile):
    ticker = data['ticker']
    price = data['current_price']
    
    print(f"\n{'='*80}")
    print(f"📊 STOCK ANALYSIS REPORT — {ticker} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}\n")
    
    print(f"Overall Score : {scores['overall']}/100   |   Profile: {profile}")
    rec = '🟢 STRONG BUY' if scores['overall'] >= 75 else '🟡 BUY' if scores['overall'] >= 60 else '🔴 HOLD/SELL'
    print(f"Recommendation: {rec}")
    
    print("\n🔬 Advanced Signals:")
    signals = scores['signals']
    
    print(f"• IV Rank          : {signals['ivr']['ivr']}%")
    print(f"• Altman Z-Score   : {signals['distress']['z_score']} → {signals['distress']['risk_level']}")
    print(f"• DCF Upside       : {signals['dcf'].get('upside_pct', 0):+.1f}%")
    print(f"• Earnings Surprise: {signals['earnings']['avg_surprise_pct']:+.1f}%")
    print(f"• Beta (vs SPY)    : {signals['beta']['beta']} (Alpha: {signals['beta']['alpha']})")
    
    # NEW: FinBERT News Sentiment (GPU powered, for Sentiment pillar)
    sent = signals.get("finbert_sentiment", {})
    if "error" not in sent:
        print(f"• News Sentiment   : {sent.get('overall_sentiment', 'Neutral')} (score: {sent.get('sentiment_score', 50)}/100) | +{sent.get('positive_pct', 0)}% / ~{sent.get('neutral_pct', 0)}% / -{sent.get('negative_pct', 0)}% ({sent.get('num_articles', 0)} articles) on {sent.get('device_used', 'cpu')}")
    else:
        print(f"• News Sentiment   : Neutral ({sent.get('note', sent.get('error', 'N/A'))})")
    
    # NEW MC Risk signal
    mc_risk = signals.get('mc_risk', {})
    print(f"• MC VaR 95% (1y)  : {mc_risk.get('var_95', 0)}%  |  CVaR: {mc_risk.get('cvar_95', 0)}%")
    print(f"• Simulated Vol    : {mc_risk.get('simulated_annual_vol', 0)}%  |  Drift: {mc_risk.get('annual_drift', 0)}%")
    
    # NEW: LSTM Deep Learning Forecast (GPU powered)
    lstm = signals.get('lstm_forecast', {})
    print(f"• LSTM DL Forecast : {lstm.get('predicted_next_return_pct', 0)}% next-day | {lstm.get('direction', 'N/A')} (strength: {lstm.get('signal_strength', 0)}/100 on {lstm.get('device_used', 'cpu')})")
    
    # NEW: Chronos-2 Foundation Model Forecast (zero-shot, very high GPU benefit)
    chronos = signals.get('chronos_forecast', {})
    if "error" not in chronos:
        print(f"• Chronos Forecast : {chronos.get('predicted_5d_return_pct', 0)}% (5d) | {chronos.get('direction', 'N/A')} | Range: {chronos.get('lower_10pct_return', 0)}% to {chronos.get('upper_90pct_return', 0)}% (uncert: {chronos.get('uncertainty_range_pct', 0)}%) on {chronos.get('device_used', 'cpu')}")
    else:
        print(f"• Chronos Forecast : {chronos.get('error', 'N/A')}")
    
    # NEW: NHITS SOTA Neural Forecast (via NeuralForecast — more accurate than LSTM/Chronos for many horizons)
    nhits = signals.get('nhits_forecast', {})
    if "error" not in nhits:
        print(f"• NHITS Forecast  : {nhits.get('predicted_5d_return_pct', 0)}% (5d) | {nhits.get('direction', 'N/A')} | {nhits.get('model', 'NHITS')} (trained {nhits.get('epochs_trained', '?')} epochs on {nhits.get('device_used', 'cpu')})")
    else:
        print(f"• NHITS Forecast  : {nhits.get('error', 'N/A')}")
    
    # NEW: PatchTST SOTA Neural Forecast (via NeuralForecast — top-tier 2024+ model with patching for efficient long-horizon forecasting)
    patchtst = signals.get('patchtst_forecast', {})
    if "error" not in patchtst:
        print(f"• PatchTST Forecast: {patchtst.get('predicted_5d_return_pct', 0)}% (5d) | {patchtst.get('direction', 'N/A')} | {patchtst.get('model', 'PatchTST')} (trained {patchtst.get('epochs_trained', '?')} epochs on {patchtst.get('device_used', 'cpu')})")
    else:
        print(f"• PatchTST Forecast: {patchtst.get('error', 'N/A')}")
    
    # NHITS + TFT + PatchTST Ensemble (all 3 SOTA models)
    ensemble = signals.get('ensemble_forecast', {})
    if "error" not in ensemble:
        print(f"• Ensemble Forecast: {ensemble.get('predicted_5d_return_pct', 0)}% (5d) | {ensemble.get('direction', 'N/A')} | Uncertainty: ±{ensemble.get('uncertainty_pct', 0)}% ({ensemble.get('models_used', 3)} models) on {ensemble.get('device_used', 'cpu')}")
    else:
        print(f"• Ensemble Forecast: {ensemble.get('error', 'N/A')}")
    
    print(f"\n📈 Monte Carlo (10,000 paths - 12 months):")
    print(f"   Median Target : ${mc_result['median']:.2f}  (+{(mc_result['median']/price-1)*100:+.1f}%)")
    print(f"   10th–90th     : ${mc_result['p10']:.2f} — ${mc_result['p90']:.2f}")
    
    # NEW: Risk pillar
    print(f"\n⚠️  Risk Score      : {scores.get('risk', 70)}/100  (from MC simulation)")
    
    print("\n" + "="*80)

def generate_json_report(data, scores, mc_result, profile):
    output = {
        "timestamp": datetime.now().isoformat(),
        "ticker": data['ticker'],
        "current_price": data['current_price'],
        "overall_score": scores['overall'],
        "profile": profile,
        "recommendation": "BUY" if scores['overall'] >= 70 else "HOLD" if scores['overall'] >= 50 else "SELL",
        "confidence": round(scores['overall'] / 100, 2),
        "pillars": {
            "fundamentals": scores['fundamentals'],
            "technicals": scores['technicals'],
            "valuation": scores['validation'],
            "sentiment": scores['sentiment'],
            "esg_quality": scores['esg_quality'],
            "risk": scores.get('risk', 70)  # NEW
        },
        "signals": scores['signals'],
        "monte_carlo": mc_result,
        "suggested_action": {
            "action": "BUY" if scores['overall'] >= 70 else "HOLD",
            "risk_percent": 1.5,
            "stop_loss": round(data['current_price'] * 0.85, 2),
            "take_profit": round(mc_result['median'], 2)
        }
    }
    
    filename = f"signals_{data['ticker']}.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    return filename
