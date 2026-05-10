#!/usr/bin/env python3
"""
Stock Analysis Skill v4.2 — Advanced Quantitative Signals + Monte Carlo Simulations
"""
import argparse
import yfinance as yf
from datetime import datetime
from score import calculate_pillars
from montecarlo import run_monte_carlo
from report import generate_report, generate_json_report

def main():
    parser = argparse.ArgumentParser(description="Advanced Stock Analysis with Signals & Simulations")
    parser.add_argument("ticker", type=str, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument("--profile", choices=["Balanced", "Growth", "Value", "Momentum"], default="Balanced",
                        help="Investor profile for weighting")
    parser.add_argument("--output", choices=["report", "json", "both"], default="both",
                        help="Output format")
    parser.add_argument("--mc-paths", type=int, default=10000, help="Number of Monte Carlo paths")
    args = parser.parse_args()
    
    ticker = args.ticker.upper()
    print(f"🔍 Analyzing {ticker} with profile={args.profile}...")
    
    # Fetch core data
    stock = yf.Ticker(ticker)
    info = stock.info
    hist = stock.history(period="1y")
    current_price = hist['Close'].iloc[-1] if not hist.empty else 0
    
    data = {
        "ticker": ticker,
        "info": info,
        "current_price": current_price,
        "history": hist
    }
    
    # Calculate scores & signals (now includes MC risk simulation)
    scores = calculate_pillars(data, profile=args.profile)
    
    # Run price projection Monte Carlo
    mc_result = run_monte_carlo(ticker, paths=args.mc-paths)
    
    # Output
    if args.output in ["report", "both"]:
        generate_report(data, scores, mc_result, args.profile)
    
    if args.output in ["json", "both"]:
        filename = generate_json_report(data, scores, mc_result, args.profile)
        print(f"\n📁 JSON saved to: {filename}")
    
    print(f"\n✅ Analysis complete for {ticker}. Overall Score: {scores['overall']}/100")

if __name__ == "__main__":
    main()
