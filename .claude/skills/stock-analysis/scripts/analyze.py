import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from fetch_data import fetch_stock_data
from score import calculate_pillars
from montecarlo import run_monte_carlo
from report import generate_report, generate_json_report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", help="Stock ticker symbol")
    parser.add_argument("--profile", default="Balanced", choices=["Balanced", "Growth", "Value", "Momentum"])
    parser.add_argument("--output", default="both", choices=["report", "json", "both"])
    args = parser.parse_args()
    
    print(f"🔍 Analyzing {args.ticker} with {args.profile} profile...\n")
    
    data = fetch_stock_data(args.ticker)
    scores = calculate_pillars(data, args.profile)
    
    annual_vol_pct = data.get('annual_vol', data['info'].get('beta', 1.0) * 25)
    mc_result = run_monte_carlo(
        current_price=data['current_price'],
        annual_vol_pct=annual_vol_pct,
        composite_score=scores['overall'],
        days=252
    )
    
    if args.output in ["report", "both"]:
        generate_report(data, scores, mc_result, args.profile)
    
    if args.output in ["json", "both"]:
        json_path = generate_json_report(data, scores, mc_result, args.profile)
        print(f"✅ JSON signal file generated: {json_path}")
    
    print(f"\n🎯 Overall Score: {scores['overall']}/100")

if __name__ == "__main__":
    main()