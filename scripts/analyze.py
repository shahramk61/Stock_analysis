#!/usr/bin/env python3
"""
Root scripts/analyze.py — uses scripts/score.py + scripts/report.py
with shared modules (fetch_data, montecarlo, dcf) from the skills pipeline.
"""
import sys, os, argparse, json

# Skills pipeline provides fetch_data, montecarlo, dcf
SKILLS_DIR = os.path.join(os.path.dirname(__file__), '..', '.claude', 'skills', 'stock-analysis', 'scripts')
sys.path.insert(0, SKILLS_DIR)
sys.path.insert(0, os.path.dirname(__file__))  # root scripts/ first (score, report, signals)

from fetch_data import fetch_stock_data
from score import calculate_pillars
from montecarlo import run_monte_carlo
from dcf import calculate_dcf
from report import generate_report, generate_json_report


def main():
    parser = argparse.ArgumentParser(description="Stock Analysis (root pipeline)")
    parser.add_argument("ticker",    help="Stock ticker symbol, e.g. AAPL")
    parser.add_argument("--profile", default="Balanced",
                        choices=["Balanced", "Growth", "Value", "Momentum"])
    parser.add_argument("--output",  default="both",
                        choices=["report", "json", "both"])
    args = parser.parse_args()

    ticker = args.ticker.upper()
    print(f"🔍 Analyzing {ticker} with {args.profile} profile...\n")

    data   = fetch_stock_data(ticker)
    data['dcf'] = calculate_dcf(data)
    scores = calculate_pillars(data, args.profile)

    vol   = data.get('annual_vol', data['info'].get('beta', 1.0) * 25)
    mc    = run_monte_carlo(data['current_price'], vol, scores['overall'], days=252)

    if args.output in ("report", "both"):
        generate_report(data, scores, mc, args.profile)

    if args.output in ("json", "both"):
        path = generate_json_report(data, scores, mc, args.profile)
        print(f"✅ JSON saved: {path}")

    print(f"🎯 Overall Score: {scores['overall']}/100")


if __name__ == "__main__":
    main()
