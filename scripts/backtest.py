#!/usr/bin/env python3
"""
CLI for the Stock Analysis backtester.

Execution model: signal at decision close → fill next open; daily stop on low;
flat exits; cash-capped sizing; BH on test window only.

Examples:
  python scripts/backtest.py AAPL --start 2024-01-01 --end 2024-12-31 --fast --export
  python scripts/backtest.py MSFT --start 2023-06-01 --fast --no-forecasts --validate
"""

import argparse
import json
import os
import sys
from datetime import date

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from backtest.engine import Backtester
from backtest.metrics import summarize


def main():
    parser = argparse.ArgumentParser(description="Backtest the Stock Analysis agent (strict execution)")
    parser.add_argument("ticker", nargs="?", default="AAPL", help="Ticker to backtest")
    parser.add_argument("--start", default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date (default today)")
    parser.add_argument("--profile", default="Balanced", choices=["Balanced", "Growth", "Value", "Momentum"])
    parser.add_argument("--capital", type=float, default=100000.0, help="Starting capital")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk per trade as fraction of capital")
    parser.add_argument("--rebalance-days", type=int, default=5, help="Decision every N trading days")
    parser.add_argument("--fast", action="store_true", help="Skip GPU/forecast retrain (recommended)")
    parser.add_argument("--no-forecasts", action="store_true", help="Disable neural forecasting signals")
    parser.add_argument("--debate", action="store_true", help="Include quant debate commentary in decisions")
    parser.add_argument("--export", action="store_true", help="Write backtest_decisions_<TICKER>.json")
    parser.add_argument("--validate", action="store_true", help="Print validation notes + export")
    parser.add_argument("--memory", dest="memory", action="store_true", default=True,
                        help="Enable decision memory (stop cooldown / loss streak) — default on")
    parser.add_argument("--no-memory", dest="memory", action="store_false",
                        help="Disable decision memory (stateless policy)")
    parser.add_argument("--journal", action="store_true",
                        help="Persist episodic run under journal/runs/ (Abzu-style)")
    args = parser.parse_args()

    print(
        f"Running backtest {args.ticker} {args.start} → {args.end or 'today'} | "
        f"capital=${args.capital:,.0f} risk={args.risk*100:.1f}% rebalance={args.rebalance_days}d | "
        f"fast={args.fast} forecasts={not args.no_forecasts and not args.fast} memory={args.memory}"
    )
    print("Execution: next-open fill · daily stop-on-low · flat exits · cash-capped size · BH on window only")
    if args.memory:
        print("Memory: stop cooldown + loss-streak size cuts (walk-forward safe; see journal/README.md)")

    x_pre = None
    if args.debate:
        xfile = f"x_sentiment_{args.ticker}.json"
        if os.path.exists(xfile):
            try:
                with open(xfile) as f:
                    x_pre = json.load(f)
                print(f"Loaded X/social pre-fetch: {xfile}")
            except Exception as e:
                print(f"Warning: could not load {xfile}: {e}")

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
        x_pre_fetched=x_pre,
        use_forecasts=not args.no_forecasts,
        use_memory=args.memory,
    )
    result = bt.run()

    print("\n" + "=" * 72)
    print(f"BACKTEST — {args.ticker}  {args.start} → {args.end or 'today'}")
    print("=" * 72)
    print(summarize(result))
    print()
    print(f"  Starting capital : ${args.capital:,.2f}")
    print(f"  Final equity     : ${result.final_equity:,.2f}  ({(result.final_equity / args.capital - 1) * 100:+.2f}%)")
    if "bh_total_return" in result.metrics:
        print(f"  Buy & hold       : {result.metrics['bh_total_return']:+.2f}%  (window only)")
        print(f"  vs Buy & hold    : {result.metrics.get('vs_bh', 0):+.2f}%")
    print(f"  Execution model  : {result.metrics.get('execution_model', 'n/a')}")
    print(f"  Fundamentals PIT : {result.metrics.get('fundamentals_pit', False)} (live info disabled in replay)")
    print()
    print("  Metrics:")
    for k in [
        "total_return", "cagr", "sharpe", "max_drawdown",
        "num_trades", "num_closed_trades", "win_rate", "expectancy_per_trade",
        "num_decisions",
    ]:
        if k in result.metrics:
            val = result.metrics[k]
            suffix = "%" if k in ("total_return", "cagr", "max_drawdown", "win_rate") else ""
            print(f"    {k:22s}: {val}{suffix}")

    print(f"\n  Trades: {len(result.trades)}")
    for i, t in enumerate(result.trades, 1):
        print(
            f"    {i}. {t.get('entry_date')} @ {t.get('entry_price')} → "
            f"{t.get('exit_date', 'open')} @ {t.get('exit_price', '-')}  "
            f"pnl={t.get('pnl', 'n/a')}  reason={t.get('exit_reason', '?')}  "
            f"shares={t.get('shares')}  score={t.get('score')}"
        )

    # Decision summary from result.decisions (not every equity day)
    decs = getattr(result, "decisions", []) or []
    if decs:
        longs = sum(1 for d in decs if d.get("action") == "long")
        flats = sum(1 for d in decs if d.get("action") == "flat")
        scores = [d["overall_score"] for d in decs if d.get("overall_score") is not None]
        avg = sum(scores) / len(scores) if scores else 0
        mem_blocks = sum(1 for d in decs if "memory block" in str(d.get("rationale") or ""))
        print(f"\n  Decisions: {len(decs)}  long={longs} flat={flats}  avg_score={avg:.1f}")
        if mem_blocks:
            print(f"  Memory blocks (cooldown): {mem_blocks}")
        print(f"  Sample rationale: {(decs[0].get('rationale') or '')[:140]}")
        # last decision with memory flags
        for d in reversed(decs):
            if d.get("memory_flags"):
                print(f"  Example memory flags: {d.get('memory_flags')} (on {d.get('date')})")
                break

    if args.validate:
        print("\n--- Validation notes ---")
        print("• Prices: signals use hist ≤ decision date (asof slice).")
        print("• Fills: next trading open after decision (not same-bar close).")
        print("• Stops: checked daily using low; gap-through fills at open.")
        print("• Flat: schedules exit next open.")
        print("• Size: risk-based, notional capped at 95% of cash.")
        print("• BH: start/end prices of the test window only (warm-up excluded).")
        print("• Fundamentals: yfinance `info` NOT used in replay (no live PE/ROE leak).")
        print("  Note: some signal helpers still call yf.Ticker for altman/piotroski/etc. — residual look-ahead risk.")
        print(f"• Metrics total_return uses initial capital ${args.capital:,.0f}.")
        print("• Memory: only decisions/trades with dates ≤ asof; stop cooldown + loss streak (journal/).")

    if args.export or args.validate or args.journal:
        out_path = f"backtest_decisions_{args.ticker}.json"
        payload = {
            "meta": {
                "ticker": args.ticker,
                "start": args.start,
                "end": args.end or str(date.today()),
                "profile": args.profile,
                "capital": args.capital,
                "risk_per_trade": args.risk,
                "rebalance_days": args.rebalance_days,
                "fast": args.fast,
                "forecasts": not args.no_forecasts and not args.fast,
                "debate": args.debate,
                "memory": args.memory,
                "execution_model": result.metrics.get("execution_model"),
            },
            "summary": {
                "final_equity": result.final_equity,
                "metrics": result.metrics,
                "num_decisions": len(decs),
                "num_trades": len(result.trades),
            },
            "decisions": decs,
            "trades": result.trades,
            "memory": getattr(result, "memory_export", None),
            "equity_curve": [
                {
                    "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                    "equity": float(row.equity),
                    "price": float(row.price),
                    "position": float(row.position),
                }
                for idx, row in result.equity_curve.iterrows()
            ] if result.equity_curve is not None and not result.equity_curve.empty else [],
        }
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"\nExported: {out_path}")

    if args.journal and getattr(result, "memory_export", None):
        from backtest.memory import DecisionMemory, MemoryConfig
        # Rebuild memory object for save helper
        mem = DecisionMemory(ticker=args.ticker, config=MemoryConfig(enabled=True))
        mem.decisions = list(result.decisions or [])
        mem.trades = list(result.trades or [])
        mem.snapshots = list((result.memory_export or {}).get("snapshots") or [])
        repo_root = os.path.abspath(os.path.join(SCRIPTS_DIR, ".."))
        jpath = mem.save_journal_run(
            repo_root,
            start=args.start,
            end=args.end or str(date.today()),
            metrics=result.metrics,
        )
        print(f"Journal run saved: {jpath}")


if __name__ == "__main__":
    main()
