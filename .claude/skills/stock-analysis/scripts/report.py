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
    print(f"• DCF Upside       : {signals['dcf'].get('upside', 0):+.1f}%")
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
    print(f"• Amihud Illiq     : {signals['amihud']}")
    print(f"• Share Turnover   : {signals['turnover']}%")
    
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
