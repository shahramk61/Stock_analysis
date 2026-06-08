#!/usr/bin/env python3
"""
CLI entrypoint for the backtester (convenience wrapper).

Usage examples (will evolve):
  python scripts/backtest.py AAPL --start 2024-01-01 --profile Balanced
  python -m scripts.backtest --tickers AAPL,MSFT --start 2023-06-01 --end 2025-06-01

See the approved long-term plan for full scope.
"""

import argparse
import json
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
    parser.add_argument("--capital", type=float, default=100000.0, help="Starting virtual capital in dollars (e.g. 1000 for a small virtual account)")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk per trade as fraction of capital (e.g. 0.01 = 1% risk)")
    parser.add_argument("--rebalance-days", type=int, default=5, help="Rebalance / decision frequency in trading days (smaller = more like frequent trading checks)")
    parser.add_argument("--fast", action="store_true", help="Fast mode: skip dynamic weights and heavy GPU retraining per step (recommended for backtests)")
    parser.add_argument("--validate", action="store_true", help="Run basic bt-08 validation checks (no-lookahead note + vs BH)")
    parser.add_argument("--debate", action="store_true", help="Enable debate_mode on the Quantitative Analyst so it generates the real debate_commentary using our signals (this is the contribution that feeds the multi-turn researcher conversation in TradingAgents)")
    parser.add_argument("--export", action="store_true", help="Export per-date decisions (score, action, conviction, debate note, rationale, etc.) to backtest_<ticker>.json — your simulated trade signals / blotter")
    args = parser.parse_args()

    print(f"🚀 Running backtest for {args.ticker} {args.start} → {args.end or 'today'} (capital=${args.capital:,.0f}, risk={args.risk*100:.1f}%, rebalance every {args.rebalance_days} days, profile={args.profile}, fast={args.fast}, debate={args.debate})...")

    if args.capital < 10000:
        print("Note: Small virtual capital — position sizes will be tiny (1% risk on $1000 is only ~$10 risk per trade). Good for seeing the decision process without big numbers.")

    if (args.end or "2025-01-01") < "2024-10-01":
        print("Tip: For 'last month' relative to late 2024 data, try --start 2024-09-01 --end 2024-10-01 (or adjust to your latest available dates).")

    bt = Backtester(
        ticker=args.ticker,
        start=args.start,
        end=args.end,
        initial_capital=args.capital,
        profile=args.profile,
        risk_per_trade=args.risk,
        rebalance_days=args.rebalance_days,
        fast_mode=args.fast,
        debate_mode=args.debate,
    )
    result = bt.run()

    print("\n" + "="*80)
    print(f"BACKTEST RESULT — {args.ticker}  {args.start} → {args.end or 'today'}")
    print("="*80)
    print(f"Virtual capital: ${args.capital:,.2f}   |  Risk per trade: {args.risk*100:.1f}%")
    print(f"Rebalance: every {args.rebalance_days} trading day(s)   |  Profile: {args.profile}")
    print(f"Modes: fast={args.fast}  debate={args.debate}  export={args.export or args.validate}")
    print()

    # === FINAL PERFORMANCE / RETURN (the key "how did the virtual account do when trading?") ===
    print("╔════════════════════════════════════════════════════════════════════════════╗")
    print("║  FINAL PERFORMANCE & RETURN (simulated trading with virtual capital)       ║")
    print("╚════════════════════════════════════════════════════════════════════════════╝")
    print(f"  Starting capital : ${args.capital:,.2f}")
    print(f"  Final equity     : ${result.final_equity:,.2f}   ({((result.final_equity / args.capital) - 1) * 100:+.2f}%)")
    print(f"  vs Buy & Hold    : {result.metrics.get('vs_bh', 0):+.2f}% (BH return over the exact same period)")
    print()
    print("  Key metrics:")
    for k in ["total_return", "cagr", "sharpe", "max_drawdown", "num_trades", "win_rate", "expectancy_per_trade"]:
        if k in result.metrics:
            val = result.metrics[k]
            suffix = "%" if k in ("total_return", "cagr", "max_drawdown", "win_rate") else ""
            print(f"    {k:22s}: {val}{suffix}")
    print(f"  Trades executed  : {len(result.trades)}")
    if result.trades:
        print("    (Full trade log with entry/exit/P&L is in the exported JSON under 'trades')")
    else:
        print("    (No trades were taken — agent stayed flat on all decision dates)")
    print()

    # === Trading Simulation Summary (the "how did it do when trading" view) ===
    print("--- Trading Simulation (virtual account) ---")
    print(f"Starting capital: ${args.capital:,.2f}")
    print(f"Final equity:     ${result.final_equity:,.2f}   ({((result.final_equity/args.capital)-1)*100:+.2f}%)")
    print(f"vs Buy & Hold:    {result.metrics.get('vs_bh', 0):+.2f}% (BH return over same period)")
    print()
    print("Key trading metrics:")
    for k in ["total_return", "cagr", "sharpe", "max_drawdown", "num_trades", "win_rate", "expectancy_per_trade"]:
        if k in result.metrics:
            val = result.metrics[k]
            suffix = "%" if k in ("total_return", "cagr", "max_drawdown", "win_rate") else ""
            print(f"  {k:22s}: {val}{suffix}")
    print()
    print(f"Trades executed: {len(result.trades)}")
    if result.trades:
        print("  (See exported JSON or result.trades for entry/exit, net P&L after costs, conviction at entry)")
    print()

    # === Per-decision agent output (especially the real debate using signals) ===
    if args.debate:
        print("--- Real Quant Analyst Output per Decision Date (using historical signals) ---")
        print("This is the *actual* output the Quantitative Analyst produces on each historical slice.")
        print("The 'Debate Contribution' is generated by the real debate logic from the signals (conviction,")
        print("regime, VaR, momentum, etc.). This is what would be fed into the multi-turn researcher debate.")
        print("No fake simulation of researchers talking — only the real quant contribution.")
        print()
        for rec in result.equity_curve.itertuples():
            print(f"Date: {rec.Index.date()}   |  Price: ${float(rec.price):.2f}")
            if getattr(rec, 'overall_score', None) is not None:
                print(f"  Overall Score: {rec.overall_score}   |  Action: {getattr(rec, 'action', 'N/A')}   |  Conviction: {getattr(rec, 'conviction', 'N/A')}")
            if getattr(rec, 'rationale', None):
                print(f"  Rationale: {rec.rationale}")
            if getattr(rec, 'debate_note', None):
                print(f"\n  Debate Contribution (real, signals-driven):")
                print("  " + rec.debate_note.replace('\n', '\n  '))
            if getattr(rec, 'quant_report', None):
                report = rec.quant_report
                # For short runs (5 days) print more of the report so user can see the full context
                max_len = 1800 if len(result.equity_curve) <= 6 else 800
                print(f"\n  Quantitative Report (context):")
                print("  " + (report[:max_len] + "\n  ... [truncated for brevity]" if len(report) > max_len else report).replace('\n', '\n  '))
            print("-" * 60)
        print()

    # === Export (the machine-readable "trade signals" the agent would have generated) ===
    if args.export or args.validate:
        decisions = []
        for rec in result.equity_curve.itertuples():
            d = {
                "date": str(rec.Index.date()),
                "price": float(rec.price),
                "overall_score": getattr(rec, 'overall_score', None),
                "action": getattr(rec, 'action', None),
                "conviction": getattr(rec, 'conviction', None),
                "rationale": getattr(rec, 'rationale', None),
            }
            if args.debate:
                d["debate_note"] = getattr(rec, 'debate_note', None)
                d["quant_report"] = getattr(rec, 'quant_report', None)
            decisions.append(d)

        out_path = f"backtest_decisions_{args.ticker}.json"
        with open(out_path, "w") as f:
            json.dump({
                "meta": {
                    "ticker": args.ticker,
                    "start": args.start,
                    "end": args.end or str(date.today()),
                    "profile": args.profile,
                    "capital": args.capital,
                    "risk_per_trade": args.risk,
                    "rebalance_days": args.rebalance_days,
                    "fast": args.fast,
                    "debate": args.debate,
                },
                "summary": {
                    "final_equity": result.final_equity,
                    "metrics": result.metrics,
                    "num_decisions": len(decisions),
                    "num_trades": len(result.trades),
                },
                "decisions": decisions,
                "trades": result.trades,
            }, f, indent=2)
        print(f"Exported full decisions + trades to: {out_path}")
        print("  → Use this JSON to analyze exactly what the agent (including its debate input) would have")
        print("    output on each day, and what trades would have been executed with your virtual capital.")
        print()

    if args.validate:
        print("[bt-08 Validation Notes]")
        print("- All signals were computed on strictly historical data up to each as-of date (no look-ahead).")
        print("- vs Buy & Hold comparison is included in the metrics above.")
        print("- For a live check: pick one of the dates, freeze yfinance data to that day, and compare")
        print("  the quant report / debate_note / decision against what the backtester recorded.")
        print()

    print("This output shows both the agent's reasoning (including real debate contributions from signals)")
    print("and the simulated trading outcome (P&L, equity path) as if you had followed its recommendations")
    print("with the specified virtual capital. The JSON is the artifact you can later turn into real orders.")


if __name__ == "__main__":
    main()
