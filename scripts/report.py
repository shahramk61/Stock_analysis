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
    
    # === MULTI-HORIZON DAILY FORECASTS (v4.11) ===
    multi = signals.get('multi_horizon_forecasts', {})
    if "error" not in multi and "horizons" in multi:
        model_names = ["NHITS", "TFT", "PatchTST", "NBEATS", "TCN"]
        W = 110

        print(f"\n{'='*W}")
        print(f"📅 Multi-Horizon Daily Forecasts (Day-by-Day) — 5 SOTA Models")
        print(f"{'='*W}")

        # Summary table
        print(f"\n{'Horizon':<7} {'Median%':<9} {'Avg%':<8} {'Direction':<14} {'±Uncert':<9} " +
              "  ".join(f"{m:<9}" for m in model_names))
        print("-" * W)
        for h in ["5d", "10d", "15d", "20d"]:
            hd = multi["horizons"].get(h, {})
            if "error" in hd:
                print(f"{h:<7} {'ERROR'}")
                continue
            pm = hd.get("per_model", {})
            tcn = pm.get("TCN", 0)
            outlier = " ⚠️TCN" if abs(tcn) > 3.0 else ""
            print(f"{h:<7} {hd.get('median_return_pct', 0):>+7.2f}%  "
                  f"{hd.get('avg_return_pct', 0):>+7.2f}%  "
                  f"{hd.get('direction', 'N/A'):<14} "
                  f"±{hd.get('model_disagreement', 0):>5.2f}%  " +
                  "  ".join(f"{pm.get(m, 0):>+7.2f}%" for m in model_names) + outlier)
        print("-" * W)
        print(f"Trend: {multi.get('trend_signal','N/A')}  |  Consensus: {multi.get('consensus_direction','N/A')}")

        # Day-by-day breakdown per horizon
        for h in ["5d", "10d", "15d", "20d"]:
            hd = multi["horizons"].get(h, {})
            if "error" in hd:
                continue
            daily  = hd.get("daily_forecasts", [])
            pm_d   = hd.get("per_model_daily", {})
            if not daily:
                continue

            print(f"\n{h} Horizon → Median: {hd.get('median_return_pct',0):+.2f}% | "
                  f"Consensus: {hd.get('direction','N/A')}")
            hdr = f"  {'Day':>4} | {'Median%':>8} | " + " | ".join(f"{m:>8}" for m in model_names)
            print(f"  {'-'*len(hdr)}")
            print(hdr)
            print(f"  {'-'*len(hdr)}")
            for i, med in enumerate(daily):
                day_num = i + 1
                is_last = (day_num == len(daily))
                per_m   = "  ".join(
                    f"{pm_d[m][i]:>+7.2f}%" if m in pm_d and i < len(pm_d[m]) else f"{'N/A':>8}"
                    for m in model_names
                )
                # For 10d/15d/20d only print first 5 days and last day to keep output compact
                if len(daily) > 5 and not (day_num <= 5 or is_last):
                    if day_num == 6:
                        print(f"  {'...':>5}")
                    continue
                outlier_flag = ""
                if is_last:
                    tcn_last = pm_d.get("TCN", [0])[-1] if "TCN" in pm_d else 0
                    if abs(tcn_last) > 3.0:
                        outlier_flag = "  ⚠️ TCN outlier"
                print(f"  {day_num:>4} | {med:>+7.3f}% | {per_m}{outlier_flag}")
            print(f"  {'-'*len(hdr)}")
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
