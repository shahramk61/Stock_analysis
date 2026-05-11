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
    
    # === IMPROVED MULTI-HORIZON SECTION (v4.10) ===
    multi = signals.get('multi_horizon_forecasts', {})
    if "error" not in multi and "horizons" in multi:
        print("\n📅 Multi-Horizon Forecasts (5d / 10d / 15d / 20d) — Ensemble of 5 SOTA Models")
        print("-" * 100)
        print(f"{'Horizon':<6} {'Median%':<8} {'Direction':<12} {'±Uncert':<9} {'Avg%':<7} {'NHITS':<7} {'TFT':<7} {'PatchTST':<9} {'NBEATS':<8} {'TCN':<8} Outliers")
        print("-" * 100)

        for h in ["5d", "10d", "15d", "20d"]:
            if h in multi["horizons"]:
                h_data = multi["horizons"][h]
                models = h_data.get("per_model", {})

                median_ret = h_data.get("median_return_pct", h_data.get("predicted_return_pct", 0))
                avg_ret = h_data.get("avg_return_pct", 0)
                direction = h_data.get("direction", "Neutral ➕")
                uncert = h_data.get("model_disagreement", 0)

                outlier_note = ""
                tcn_val = models.get("TCN", 0)
                if h == "5d" and abs(tcn_val) > 4.0:
                    outlier_note = "⚠️ TCN Bearish Outlier"
                elif abs(tcn_val) > 3.0:
                    outlier_note = "⚠️ TCN outlier"

                print(f"{h:<6} {median_ret:+6.1f}%  {direction:<12} ±{uncert:4.1f}%   {avg_ret:+6.1f}%  "
                      f"{models.get('NHITS',0):+6.1f}% {models.get('TFT',0):+6.1f}% {models.get('PatchTST',0):+6.1f}% "
                      f"{models.get('NBEATS',0):+6.1f}% {tcn_val:+6.1f}%  {outlier_note}")

        print("-" * 100)
        print(f"Overall Trend: {multi.get('trend_signal', 'N/A')} | Consensus: {multi.get('consensus_direction', 'Neutral ➕')}")
    else:
        print(f"\n📅 Multi-Horizon Forecasts: {multi.get('error', 'Not available')}")
    
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
