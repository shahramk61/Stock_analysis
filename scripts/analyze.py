#!/usr/bin/env python3
"""
Root scripts/analyze.py — uses scripts/score.py + scripts/report.py
with shared modules (fetch_data, montecarlo, dcf) from the skills pipeline.
"""
import argparse
import json

import _pipeline  # noqa: F401 — ensures scripts/ is on sys.path

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
    parser.add_argument("--dynamic-weights", action="store_true",
                        help="Compute dynamic ensemble weights from out-of-sample backtest (~2x slower)")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    print(f"🔍 Analyzing {ticker} with {args.profile} profile" +
          (" + dynamic weights" if args.dynamic_weights else "") + "...\n")

    data   = fetch_stock_data(ticker)
    data['dcf'] = calculate_dcf(data)
    scores = calculate_pillars(data, args.profile, compute_dynamic_weights=args.dynamic_weights)

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
