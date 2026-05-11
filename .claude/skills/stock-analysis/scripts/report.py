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
    print(f"Recommendation: {'🟢 STRONG BUY' if scores['overall'] >= 75 else '🟡 BUY' if scores['overall'] >= 60 else '🔴 HOLD/SELL'}")
    
    print("\n🔬 Advanced Signals:")
    signals = scores['signals']
    
    print(f"• IV Rank          : {signals['ivr']['ivr']}%")
    print(f"• Altman Z-Score   : {signals['distress']['z_score']} → {signals['distress']['risk_level']}")
    print(f"• DCF Upside       : {signals['dcf'].get('upside_pct', 0):+.1f}%")
    print(f"• Earnings Surprise: {signals['earnings']['avg_surprise_pct']:+.1f}%")
    print(f"• Beta (vs SPY)    : {signals['beta']['beta']} (Alpha: {signals['beta']['alpha']})")
    print(f"• Piotroski F-Score: {signals['piotroski']}/9")
    print(f"• ATR Vol Cluster  : {signals['atr_vol']['atr_percent']}% ({signals['atr_vol']['vol_clustering']})")
    print(f"• Rel Strength SPY : {signals['rs']['rs_spy']:+.1f}% (Sector: {signals['rs']['rs_sector']:+.1f}%)")
    print(f"• Market Regime    : {signals['regime']['regime']} (probs: {signals['regime']['probs']})")
    print(f"• GARCH Vol Fcst   : {signals['garch']['garch_vol_forecast']}% (ratio: {signals['garch']['vol_ratio']})")
    print(f"• Momentum 6m/12m  : {signals['momentum']['momentum_6m']}% / {signals['momentum']['momentum_12m']}%")
    print(f"• 52w High Dist    : {signals['momentum']['dist_to_52w_high']}% {'(Near High ✓)' if signals['momentum']['near_52w_high'] else ''}")
    print(f"• Gross Profitab.  : {signals['quality']['gross_profitability']}%")
    print(f"• Accruals         : {signals['quality']['accruals']}% {'(Low ✓)' if signals['quality']['high_quality'] else ''}")
    print(f"• Amihud Illiq     : {signals['amihud'].get('amihud', 0):.6f}")
    print(f"• Share Turnover   : {signals['turnover'].get('turnover', 0):.1f}%")
    print(f"• Vol-Price Corr   : {signals['vol_price']['vol_price_corr']} ({signals['vol_price']['interpretation']})")
    print(f"• Formulaic Alpha  : {signals['formulaic_alpha']['alpha']} ({signals['formulaic_alpha']['alpha_signal']})")
    print(f"• OBV (20d chg)    : {signals['obv']['obv_change_20d_pct']}%")
    print(f"• Chaikin MF       : {signals['cmf']['cmf']} ({signals['cmf']['cmf_signal']})")
    mc_risk = signals.get('mc_risk', {})
    if mc_risk:
        rl = mc_risk.get('risk_level', 'N/A')
        re = '🔴' if rl == 'High' else ('🟡' if rl == 'Medium' else '🟢')
        print(f"• MC VaR 95%       : {mc_risk.get('var_95', 0):.1f}% | CVaR 95%: {mc_risk.get('cvar_95', 0):.1f}% | Risk: {re} {rl} | Vol: {mc_risk.get('simulated_annual_vol', 0):.1f}% | Drift: {mc_risk.get('annual_drift', 0):+.1f}%")

    # GPU / DL signals
    lstm = signals.get('lstm', {})
    finbert = signals.get('finbert', {})
    dl      = signals.get('dl_ensemble', {})
    chronos = signals.get('chronos', {})
    print(f"\n🖥️  GPU / Deep Learning Signals:")
    if 'error' not in lstm:
        preds_str = f" | steps: {lstm['all_predictions']}" if lstm.get('all_predictions') else ""
        print(f"• LSTM Forecast    : {lstm.get('predicted_return_pct', 0):+.2f}% ({lstm.get('prediction_length',1)}d) → {lstm.get('direction','N/A')} (strength: {lstm.get('signal_strength',0):.0f}/100, device: {lstm.get('device_used','?')}){preds_str}")
    else:
        print(f"• LSTM Forecast    : unavailable ({lstm.get('error','?')})")
    if 'error' not in chronos and 'predicted_return_pct' in chronos:
        print(f"• Chronos-2 Fcst   : {chronos.get('predicted_return_pct',0):+.2f}% ({chronos.get('prediction_length',5)}d) → {chronos.get('direction','N/A')} | range: {chronos.get('lower_10pct',0):+.1f}% to {chronos.get('upper_90pct',0):+.1f}% | ±{chronos.get('uncertainty_range_pct',0):.1f}% | device: {chronos.get('device_used','?')}")
    else:
        print(f"• Chronos-2 Fcst   : unavailable ({chronos.get('error','not installed')})")
    if 'error' not in finbert:
        print(f"• FinBERT Sentiment: {finbert.get('overall_sentiment','N/A')} (score: {finbert.get('sentiment_score',50):.0f}/100, {finbert.get('num_articles',0)} articles, device: {finbert.get('device_used','?')})")
    else:
        print(f"• FinBERT Sentiment: unavailable ({finbert.get('error','?')})")
    if 'error' not in dl:
        print(f"• DL Ensemble      : {dl.get('predicted_return_pct',0):+.2f}% (5d) → {dl.get('direction','N/A')} | uncertainty: ±{dl.get('uncertainty_pct',0):.2f}% | models: {dl.get('models_used',0)}/5 | device: {dl.get('device_used','?')}")
    else:
        print(f"• DL Ensemble      : unavailable ({dl.get('error','?')})")
    multi_h = signals.get('multi_h', {})
    if multi_h and 'horizons' in multi_h and not multi_h.get('error'):
        h_parts = []
        for hd in ['5d', '10d', '15d', '20d']:
            r = multi_h['horizons'].get(hd, {})
            if 'predicted_return_pct' in r:
                h_parts.append(f"{hd}: {r['predicted_return_pct']:+.1f}%")
        if h_parts:
            print(f"• Multi-Horizon    : {' | '.join(h_parts)} → {multi_h.get('consensus_direction','?')} | Trend: {multi_h.get('trend_signal','?')}")
    elif multi_h.get('error'):
        print(f"• Multi-Horizon    : unavailable ({multi_h.get('error','?')[:60]})")

    print(f"\n📈 Monte Carlo (10,000 paths - 12 months):")
    print(f"   Median Target : ${mc_result['median']:.2f}  (+{(mc_result['median']/price-1)*100:+.1f}%)")
    print(f"   10th–90th     : ${mc_result['p10']:.2f} — ${mc_result['p90']:.2f}")
    
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
        "signals": scores['signals'],
        "monte_carlo": mc_result,
        "suggested_action": {
            "action": "BUY",
            "risk_percent": 1.5,
            "stop_loss": round(data['current_price'] * 0.85, 2),
            "take_profit": round(mc_result['median'], 2)
        }
    }
    
    filename = f"signals_{data['ticker']}.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    return filename
