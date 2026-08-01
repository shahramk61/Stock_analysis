from tabulate import tabulate
import json
import os
from datetime import datetime

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

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
    lstm_preds = lstm.get('all_predictions', [])
    plen = lstm.get('prediction_length', len(lstm_preds) or 1)
    if lstm_preds:
        daily_str = " → ".join(f"{v:+.2f}%" for v in lstm_preds)
        print(f"• LSTM DL Forecast : {plen}d path: {daily_str} | {lstm.get('direction', 'N/A')} | device: {lstm.get('device_used','?')}")
    else:
        print(f"• LSTM DL Forecast : {lstm.get('predicted_return_pct', 0):+.2f}% ({plen}d) | {lstm.get('direction', 'N/A')}")
    
    # Chronos
    chronos = signals.get('chronos_forecast', {})
    if "error" not in chronos:
        plen = chronos.get('prediction_length', 5)
        c_preds = chronos.get('all_predictions', [])
        if c_preds:
            path = " → ".join(f"{v:+.2f}%" for v in c_preds)
            print(f"• Chronos Forecast : {plen}d path: {path} | {chronos.get('direction', 'N/A')}")
        else:
            print(f"• Chronos Forecast : {chronos.get('predicted_return_pct', 0)}% ({plen}d) | {chronos.get('direction', 'N/A')}")
    
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
    
    # === MULTI-HORIZON DAILY FORECASTS (v4.24: 7-model ensemble + 4 aggregation methods) ===
    multi = signals.get('multi_horizon_forecasts', {})
    if "error" not in multi and "horizons" in multi:
        model_names = ["NHITS", "TFT", "PatchTST", "NBEATS", "TCN", "LSTM", "Chronos"]
        W = 140

        print(f"\n{'='*W}")
        print(f"📅 Multi-Horizon Daily Forecasts (Day-by-Day) — 7 SOTA Models")
        print(f"{'='*W}")

        # ── Ensemble summary table (Median / Avg / Static-weighted / Dynamic-weighted)
        has_dyn = any(multi["horizons"].get(h, {}).get("weighted_dynamic_pct") is not None
                      for h in ["5d", "10d", "15d", "20d", "50d"])
        hdr = f"{'Horizon':<7} {'Median%':<9} {'Avg%':<8} {'WgtStat%':<9}"
        if has_dyn:
            hdr += f" {'WgtDyn%':<9}"
        hdr += f" {'Direction':<14} {'±Uncert':<9} " + "  ".join(f"{m:<9}" for m in model_names)
        print(f"\n{hdr}")
        print("-" * W)
        for h in ["5d", "10d", "15d", "20d", "50d"]:
            hd = multi["horizons"].get(h, {})
            if "error" in hd:
                print(f"{h:<7} {'ERROR'}")
                continue
            pm = hd.get("per_model", {})
            tcn = pm.get("TCN", 0)
            outlier = " ⚠️TCN" if abs(tcn) > 3.0 else ""
            wm_s = hd.get("weighted_static_pct")
            wm_d = hd.get("weighted_dynamic_pct")
            line  = f"{h:<7} {hd.get('median_return_pct', 0):>+7.2f}%  "
            line += f"{hd.get('avg_return_pct', 0):>+7.2f}%  "
            line += f"{wm_s if wm_s is not None else 0:>+7.2f}%  "
            if has_dyn:
                line += f"{wm_d if wm_d is not None else 0:>+7.2f}%  "
            line += f"{hd.get('direction', 'N/A'):<14} "
            line += f"±{hd.get('model_disagreement', 0):>5.2f}%  "
            line += "  ".join(f"{pm.get(m, 0):>+7.2f}%" for m in model_names) + outlier
            print(line)
        print("-" * W)
        print(f"Trend: {multi.get('trend_signal','N/A')}  |  Consensus: {multi.get('consensus_direction','N/A')}")

        # Print weight details
        sw = multi.get("static_weights", {})
        if sw:
            print(f"\nStatic weights:  " + "  ".join(f"{n}={w}" for n, w in sw.items()))
        dwi = multi.get("dynamic_weights_info")
        if dwi:
            dw = dwi.get("weights", {})
            de = dwi.get("errors_mae", {})
            print(f"Dynamic weights (val_h={dwi.get('val_h')}):  " + "  ".join(f"{n}={w}" for n, w in dw.items()))
            print(f"Dynamic MAE:   " + "  ".join(f"{n}={e}%" for n, e in de.items()))

        # Day-by-day breakdown per horizon
        for h in ["5d", "10d", "15d", "20d", "50d"]:
            hd = multi["horizons"].get(h, {})
            if "error" in hd:
                continue
            daily       = hd.get("daily_forecasts", [])
            daily_px    = hd.get("daily_prices", [])
            pm_d        = hd.get("per_model_daily", {})
            dates       = hd.get("forecast_dates", [])
            last_px     = hd.get("last_price", price)
            if not daily:
                continue

            print(f"\n{h} Horizon → Median: {hd.get('median_return_pct',0):+.2f}% | "
                  f"Consensus: {hd.get('direction','N/A')} | Current: ${last_px:.2f}")
            hdr = (f"  {'Day':>4} | {'Date':<12} | {'Price$':>8} | {'Cumul%':>8} | " +
                   " | ".join(f"{m:>8}" for m in model_names))
            sep = f"  {'-'*len(hdr)}"
            print(sep)
            print(hdr)
            print(sep)
            for i, med in enumerate(daily):
                day_num  = i + 1
                is_last  = (day_num == len(daily))
                date_str = dates[i] if i < len(dates) else ""
                px_str   = f"${daily_px[i]:.2f}" if i < len(daily_px) else "N/A"
                per_m    = "  ".join(
                    f"{pm_d[m][i]:>+7.2f}%" if m in pm_d and i < len(pm_d[m]) else f"{'N/A':>8}"
                    for m in model_names
                )
                # For longer horizons print first 5 days + last day only
                if len(daily) > 5 and not (day_num <= 5 or is_last):
                    if day_num == 6:
                        print(f"  {'...':>5}")
                    continue
                outlier_flag = ""
                if is_last:
                    tcn_last = pm_d.get("TCN", [0])[-1] if "TCN" in pm_d else 0
                    if abs(tcn_last) > 3.0:
                        outlier_flag = "  ⚠️ TCN outlier"
                print(f"  {day_num:>4} | {date_str:<12} | {px_str:>8} | {med:>+7.3f}% | {per_m}{outlier_flag}")
            print(sep)
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
        # Align with human report + README bands (was 70/50; text report uses 75/60)
        "recommendation": (
            "STRONG_BUY" if scores['overall'] >= 75 else
            "BUY" if scores['overall'] >= 60 else
            "HOLD" if scores['overall'] >= 50 else
            "CAUTION" if scores['overall'] >= 35 else
            "SELL"
        ),
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
    
    filename = os.path.join(_REPO_ROOT, f"signals_{data['ticker']}.json")
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    return filename
