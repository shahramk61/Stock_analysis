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
    
    # FinBERT
    sent = signals.get("finbert_sentiment", {})
    if "error" not in sent:
        print(f"• News Sentiment   : {sent.get('overall_sentiment', 'Neutral')} (score: {sent.get('sentiment_score', 50)}/100)")
    else:
        print(f"• News Sentiment   : Neutral ({sent.get('note', sent.get('error', 'N/A'))})")
    
    # MC Risk
    mc_risk = signals.get('mc_risk', {})
    print(f"• MC VaR 95% (1y)  : {mc_risk.get('var_95', 0)}%  |  CVaR: {mc_risk.get('cvar_95', 0)}%")
    
    # LSTM
    lstm = signals.get('lstm_forecast', {})
    print(f"• LSTM DL Forecast : {lstm.get('predicted_next_return_pct', lstm.get('predicted_return_pct', 0))}% next-day | {lstm.get('direction', 'N/A')}")
    
    # Chronos
    chronos = signals.get('chronos_forecast', {})
    if "error" not in chronos:
        print(f"• Chronos Forecast : {chronos.get('predicted_return_pct', 0)}% ({chronos.get('prediction_length', 5)}d) | {chronos.get('direction', 'N/A')}")
    
    # NHITS + PatchTST + Ensemble (keep short)
    nhits = signals.get('nhits_forecast', {})
    if "error" not in nhits:
        print(f"• NHITS Forecast   : {nhits.get('predicted_return_pct', nhits.get('predicted_5d_return_pct', 0))}% (5d)")
    
    patchtst = signals.get('patchtst_forecast', {})
    if "error" not in patchtst:
        print(f"• PatchTST Forecast: {patchtst.get('predicted_return_pct', patchtst.get('predicted_5d_return_pct', 0))}% (5d)")
    
    ensemble = signals.get('ensemble_forecast', {})
    if "error" not in ensemble:
        print(f"• Ensemble (NHITS+TFT+PatchTST): {ensemble.get('predicted_return_pct', ensemble.get('predicted_5d_return_pct', 0))}% (5d) | Uncertainty: ±{ensemble.get('uncertainty_pct', 0)}%")
    
    # Multi-Horizon Forecasts (5d / 10d / 15d / 20d) — per-model breakdown
    multi = signals.get('multi_horizon_forecasts', {})
    if "error" not in multi and "horizons" in multi:
        print("\n📅 Multi-Horizon Forecasts (5d / 10d / 15d / 20d):")
        model_names = ["NHITS", "TFT", "PatchTST", "NBEATS", "TCN"]
        # Header row
        header = f"   {'Horizon':>8}  {'Avg':>7}  {'Dir':<14}  {'Uncert':>8}  " + "  ".join(f"{m:>8}" for m in model_names)
        print(f"   {'-'*len(header)}")
        print(f"   {'Horizon':>8}  {'Avg%':>7}  {'Direction':<14}  {'±Uncert':>8}  " + "  ".join(f"{m:>8}" for m in model_names))
        print(f"   {'-'*len(header)}")
        for h in ["5d", "10d", "15d", "20d"]:
            if h in multi["horizons"]:
                h_data = multi["horizons"][h]
                if "error" in h_data:
                    print(f"   {h:>8}  {'N/A':>7}  {'Error':<14}  {'N/A':>8}")
                    continue
                avg = h_data.get('predicted_return_pct', 0)
                direction = h_data.get('direction', 'N/A')
                uncert = h_data.get('model_disagreement', 0)
                model_preds = h_data.get('model_predictions', {})
                per_model = "  ".join(
                    f"{model_preds[m]:>+7.1f}%" if m in model_preds else f"{'N/A':>8}"
                    for m in model_names
                )
                print(f"   {h:>8}  {avg:>+6.1f}%  {direction:<14}  ±{uncert:>6.2f}%  {per_model}")
        print(f"   {'-'*len(header)}")
        print(f"   Trend: {multi.get('trend_signal', 'N/A')}  |  Consensus: {multi.get('consensus_direction', 'N/A')}")
    else:
        print(f"\n📅 Multi-Horizon: {multi.get('error', 'N/A')}")
    
    print(f"\n📈 Monte Carlo (12 months): Median ${mc_result['median']:.2f}  |  Range: ${mc_result['p10']:.2f} – ${mc_result['p90']:.2f}")
    print(f"\n{'='*80}\n")


def generate_json_report(data, scores, mc_result, profile):
    output = {
        "timestamp": datetime.now().isoformat(),
        "ticker": data['ticker'],
        "current_price": data['current_price'],
        "overall_score": scores['overall'],
        "profile": profile,
        "recommendation": "BUY" if scores['overall'] >= 70 else "HOLD" if scores['overall'] >= 50 else "SELL",
        "pillars": {
            "fundamentals": scores['fundamentals'],
            "technicals": scores['technicals'],
            "valuation": scores['valuation'],
            "sentiment": scores['sentiment'],
            "esg_quality": scores['esg_quality'],
            "risk": scores.get('risk', 70)
        },
        "signals": scores['signals'],
        "monte_carlo": mc_result
    }
    
    filename = f"signals_{data['ticker']}.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    return filename
