#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from fetch_data import fetch_stock_data
from score import calculate_pillars
from montecarlo import run_monte_carlo
from dcf import calculate_dcf

tickers = sys.argv[1:] if len(sys.argv) > 1 else ['AAPL', 'AMZN']

results = {}
for ticker in tickers:
    print(f"Fetching {ticker}...", file=sys.stderr)
    data = fetch_stock_data(ticker)
    data['dcf'] = calculate_dcf(data)
    scores = calculate_pillars(data, 'Balanced')
    mc = run_monte_carlo(data['current_price'], data.get('annual_vol', 25), scores['overall'], days=252)
    sig = scores['signals']
    dcf = data['dcf']
    results[ticker] = {
        'Price':                   f"${data['current_price']:.2f}",
        'Overall Score':           f"{scores['overall']}/100",
        'Recommendation':          '🟢 BUY' if scores['overall'] >= 60 else ('🟡 HOLD' if scores['overall'] >= 50 else '🔴 SELL'),
        '':                        '',
        '─ Pillar Scores ─':       '──────────',
        'Fundamentals':            f"{scores['fundamentals']:.1f}",
        'Technicals':              f"{scores['technicals']:.1f}",
        'Valuation':               f"{scores['valuation']:.1f}",
        'Sentiment':               f"{scores['sentiment']:.1f}",
        'ESG/Quality':             f"{scores['esg_quality']:.1f}",
        ' ':                       '',
        '─ Advanced Signals ─':    '──────────',
        'IV Rank (IVR)':           f"{sig['ivr']['ivr']}%",
        'IV Skew':                 f"{sig['ivr']['skew']:.3f}",
        'Altman Z-Score':          f"{sig['distress']['z_score']} ({sig['distress']['risk_level']})",
        'Beneish M-Score':         f"{sig['distress']['m_score']}",
        'DCF Intrinsic Value':     f"${dcf['intrinsic']:.2f}" if dcf.get('available') else 'N/A',
        'DCF Upside':              f"{dcf['upside_pct']:+.1f}%" if dcf.get('available') else 'N/A',
        'DCF WACC':                f"{dcf['wacc']}%" if dcf.get('available') else 'N/A',
        'Earnings Surprise (avg)': f"{sig['earnings']['avg_surprise_pct']:+.1f}%",
        'Beta (vs SPY)':           f"{sig['beta']['beta']:.3f}",
        'Alpha (annualised)':      f"{sig['beta']['alpha']:+.4f}",
        'R-Squared':               f"{sig['beta']['r_squared']:.3f}",
        'Piotroski F-Score':       f"{sig['piotroski']}/9",
        'ATR %':                   f"{sig['atr_vol']['atr_percent']:.2f}%",
        'Vol Clustering':          sig['atr_vol']['vol_clustering'],
        'Vol Risk Level':          sig['atr_vol']['risk_level'],
        'RS vs SPY (6mo)':         f"{sig['rs']['rs_spy']:+.1f}%",
        'RS vs Sector (6mo)':      f"{sig['rs']['rs_sector']:+.1f}%",
        '  ':                      '',
        '─ Monte Carlo (12mo) ─':  '──────────',
        'Median Target':           f"${mc['median']:.2f}",
        'Expected Return':         f"{(mc['median']/data['current_price']-1)*100:+.1f}%",
        '10th Percentile':         f"${mc['p10']:.2f}",
        '90th Percentile':         f"${mc['p90']:.2f}",
        'Prob Gain >20%':          f"{mc['prob_up_20']:.1f}%",
        'Prob Loss (end<entry)':   f"{mc['prob_negative']:.1f}%",
        'Stop-Loss (-15%)':        f"${mc['stop_price']:.2f}",
    }

col_w = 26
print()
header = f"{'Metric':<{col_w}}" + "".join(f"{t:>14}" for t in tickers)
print(header)
print("─" * (col_w + 14 * len(tickers)))

all_keys = list(results[tickers[0]].keys())
for key in all_keys:
    if key.startswith('─'):
        print()
        print(f"{key:<{col_w}}")
    elif key.strip() == '':
        continue
    else:
        row = f"{key:<{col_w}}" + "".join(f"{results[t].get(key,'N/A'):>14}" for t in tickers)
        print(row)
print()
