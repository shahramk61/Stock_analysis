#!/usr/bin/env python3
"""
CLI entrypoint for the backtester (convenience wrapper).

Usage examples (will evolve):
  python scripts/backtest.py AAPL --start 2024-01-01 --profile Balanced
  python -m scripts.backtest --tickers AAPL,MSFT --start 2023-06-01 --end 2025-06-01

See the approved long-term plan for full scope.
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

# Ensure we can import sibling modules (consistent with analyze.py + _pipeline.py)
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from backtest.engine import Backtester
from backtest.metrics import summarize


def main():
    parser = argparse.ArgumentParser(description="Backtest the Stock Analysis agent")
    parser.add_argument("ticker", nargs="?", default="AAPL", help="Ticker to backtest")
    parser.add_argument("--start", default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date (default today)")
    parser.add_argument("--profile", default="Balanced", choices=["Balanced", "Growth", "Value", "Momentum"])
    parser.add_argument("--capital", type=float, default=100000.0)
    parser.add_argument("--risk", type=float, default=0.01, help="Risk per trade (fraction)")
    parser.add_argument("--fast", action="store_true", help="Fast mode: skip dynamic weights and heavy GPU retraining per step (recommended for backtests)")
    args = parser.parse_args()

    print(f"🚀 Running backtest for {args.ticker} {args.start} → {args.end or 'today'} (profile={args.profile})...")

    bt = Backtester(
        ticker=args.ticker,
        start=args.start,
        end=args.end,
        initial_capital=args.capital,
        profile=args.profile,
        risk_per_trade=args.risk,
        fast_mode=args.fast,
    )
    result = bt.run()

    print("\n=== Backtest Result (skeleton) ===")
    print(summarize(result))
    print(f"Equity curve points: {len(result.equity_curve)}")
    print(f"Trades logged: {len(result.trades)}")
    print("Metrics (partial):", result.metrics)
    print("\n(Full implementation in progress per plan. Current run uses placeholder policy.)")


if __name__ == "__main__":
    main()
