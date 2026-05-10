#!/usr/bin/env python3
"""
Stock Analysis — main entry point.
Usage:
    python analyze.py TICKER [--profile balanced|value|growth|momentum|income] [--no-esg] [--days 252]
"""
import sys
import os
import argparse
from datetime import datetime

# allow running from any directory
sys.path.insert(0, os.path.dirname(__file__))

from fetch_data import fetch_stock_data
from score import calculate_pillars, check_risk_flags
from montecarlo import run_monte_carlo
from report import generate_report


def parse_args():
    parser = argparse.ArgumentParser(description='Stock Analysis Tool')
    parser.add_argument('ticker', help='Stock ticker symbol (e.g. AAPL)')
    parser.add_argument('--profile', default='balanced',
                        choices=['balanced', 'value', 'growth', 'momentum', 'income'],
                        help='Investor profile (default: balanced)')
    parser.add_argument('--no-esg', action='store_true', help='Disable ESG/Quality pillar')
    parser.add_argument('--days', type=int, default=252, help='Monte Carlo horizon in days (default: 252)')
    parser.add_argument('--output', default=None, help='Save report to file (default: print to stdout)')
    return parser.parse_args()


def main():
    args = parse_args()
    ticker = args.ticker.upper()
    esg_enabled = not args.no_esg

    print(f"🔍 Fetching data for {ticker}...", file=sys.stderr)
    data = fetch_stock_data(ticker)

    print(f"📐 Scoring pillars ({args.profile} profile)...", file=sys.stderr)
    scores = calculate_pillars(data, profile=args.profile, esg_enabled=esg_enabled)
    risk_flags = check_risk_flags(data)

    print(f"📊 Running Monte Carlo (10,000 paths)...", file=sys.stderr)
    mc_12m = run_monte_carlo(
        current_price=data['current_price'],
        annual_vol_pct=data.get('annual_vol', 30),
        composite_score=scores['composite'],
        days=252,
    )
    mc_36m = run_monte_carlo(
        current_price=data['current_price'],
        annual_vol_pct=data.get('annual_vol', 30),
        composite_score=scores['composite'],
        days=756,
    )

    print(f"📝 Generating report...", file=sys.stderr)
    report = generate_report(
        data=data,
        scores=scores,
        mc_12m=mc_12m,
        mc_36m=mc_36m,
        profile=args.profile,
        esg_enabled=esg_enabled,
        risk_flags=risk_flags,
    )

    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"✅ Report saved to {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == '__main__':
    main()
