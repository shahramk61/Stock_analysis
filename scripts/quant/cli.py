"""
Command-line interface for Quant measurement tools.

Usage:
    python -m scripts.quant pit-score TICKER --asof YYYY-MM-DD [--hist-start YYYY-MM-DD]
    python -m scripts.quant walk-forward TICKER --start YYYY-MM-DD --end YYYY-MM-DD
    python -m scripts.quant audit
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta


def _load_hist(ticker: str, start: str, end: str = None):
    """Load OHLCV history from yfinance."""
    import pandas as pd
    import yfinance as yf

    if end is None:
        end_date = date.today()
    else:
        end_date = pd.Timestamp(end).date()

    start_date = pd.Timestamp(start).date()

    # Download with extra lookback for indicator warmup
    lookback = 400
    dl_start = start_date - timedelta(days=lookback)

    print(f"Downloading {ticker} history from {dl_start} to {end_date}...", flush=True)

    raw = yf.download(
        ticker,
        start=str(dl_start),
        end=str(end_date + timedelta(days=1)),
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if raw is None or raw.empty:
        raise ValueError(f"No data for {ticker} in range {dl_start} → {end_date}")

    # Flatten MultiIndex if present
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    # Ensure flat OHLCV columns
    ohlcv = ["Open", "High", "Low", "Close", "Volume"]
    for col in ohlcv:
        if col not in raw.columns:
            raise ValueError(f"Missing column {col} in downloaded data")

    hist = raw[ohlcv].copy()
    hist.index = pd.to_datetime(hist.index)
    if hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)

    hist = hist.sort_index().dropna(how="all")

    print(f"Loaded {len(hist)} bars from {hist.index[0].date()} to {hist.index[-1].date()}")

    return hist


def cmd_pit_score(args):
    """Run PIT score command."""
    import pandas as pd
    from scripts.quant.pit_score import compute_pit_score
    from scripts.quant.no_lookahead import patch_yfinance_guards

    ticker = args.ticker.upper()
    asof = args.asof

    # Determine history start
    if args.hist_start:
        hist_start = args.hist_start
    else:
        # Default: 2 years before asof
        asof_date = pd.Timestamp(asof).date()
        hist_start = str(asof_date - timedelta(days=730))

    # Load history
    hist = _load_hist(ticker, hist_start, asof)

    # Patch yfinance guards
    patch_yfinance_guards()

    # Compute PIT score
    print(f"\nComputing PIT score for {ticker} at {asof}...\n")
    result = compute_pit_score(
        ticker=ticker,
        asof=asof,
        hist=hist,
        profile=args.profile,
        use_forecasts=args.use_forecasts,
    )

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return 1

    # Print results
    print("=" * 80)
    print(f"POINT-IN-TIME SCORE: {ticker} at {result['asof']}")
    print("=" * 80)
    print(f"Profile: {result['profile']}")
    print(f"Overall Score: {result['overall_score']}")
    print(f"\nPillar Scores:")
    for pillar, score in result["pillar_scores"].items():
        print(f"  {pillar:15s}: {score:5.1f}")

    print(f"\nAvailability Ledger:")
    for field, status in result["availability"].items():
        symbol = "✓" if status == "computed" else ("✗" if status.startswith("unavailable") else "—")
        print(f"  {symbol} {field:20s}: {status}")

    if args.json:
        print("\n" + "=" * 80)
        print("JSON Output:")
        print(json.dumps(result, indent=2))

    return 0


def cmd_walk_forward(args):
    """Run walk-forward replay command."""
    import pandas as pd
    from scripts.quant.walkforward import run_walkforward
    from scripts.quant.no_lookahead import patch_yfinance_guards

    ticker = args.ticker.upper()
    start = args.start
    end = args.end

    # Load history (with lookback before start and extra after end for realized returns)
    start_date = pd.Timestamp(start).date()
    end_date = pd.Timestamp(end).date()
    hist_start = str(start_date - timedelta(days=400))
    hist_end = str(end_date + timedelta(days=30))

    hist = _load_hist(ticker, hist_start, hist_end)

    # Patch yfinance guards
    patch_yfinance_guards()

    # Run walk-forward
    print(f"\nRunning walk-forward replay for {ticker} from {start} to {end}...\n")
    result = run_walkforward(
        ticker=ticker,
        start=start,
        end=end,
        hist=hist,
        rebalance_days=args.rebalance_days,
        profile=args.profile,
        use_forecasts=args.use_forecasts,
        attach_realized_returns=not args.no_realized,
        realized_horizons=args.realized_horizons,
    )

    if "error" in result:
        print(f"ERROR: {result['error']}")
        return 1

    # Print results
    print("=" * 80)
    print(f"WALK-FORWARD REPLAY: {ticker}")
    print("=" * 80)
    print(f"Period: {result['start']} → {result['end']}")
    print(f"Rebalance: every {result['rebalance_days']} trading days")
    print(f"Profile: {result['profile']}")
    print(f"\nSummary:")
    for key, val in result["summary"].items():
        print(f"  {key}: {val}")

    if args.verbose:
        print(f"\nSteps ({len(result['steps'])}):")
        for step in result["steps"]:
            print(f"  {step['asof']}: score={step['score']}")
            if step.get("realized_returns"):
                for horizon, ret_data in step["realized_returns"].items():
                    print(f"    Realized {horizon}: {ret_data['return_pct']:+.2f}%")

    if args.json:
        print("\n" + "=" * 80)
        print("JSON Output:")
        print(json.dumps(result, indent=2))

    return 0


def cmd_audit(args):
    """Run no-lookahead audit command."""
    from scripts.quant.no_lookahead import audit_lookahead_risks, print_audit_report

    print("Running no-lookahead audit...\n")

    scan_paths = args.paths if args.paths else None

    fundamental_leaks, info_dict_leaks = audit_lookahead_risks(scan_paths=scan_paths)

    print_audit_report(fundamental_leaks, info_dict_leaks)

    if args.json:
        result = {
            "fundamental_leaks": fundamental_leaks,
            "info_dict_leaks": info_dict_leaks,
            "total_leaks": len(fundamental_leaks) + len(info_dict_leaks),
        }
        print("\n" + "=" * 80)
        print("JSON Output:")
        print(json.dumps(result, indent=2))

    return 1 if (fundamental_leaks or info_dict_leaks) else 0


def main():
    parser = argparse.ArgumentParser(
        description="Quant measurement tools: PIT scoring, walk-forward replay, no-lookahead audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # pit-score command
    pit_parser = subparsers.add_parser("pit-score", help="Compute point-in-time score")
    pit_parser.add_argument("ticker", help="Stock ticker (e.g. AAPL)")
    pit_parser.add_argument("--asof", required=True, help="As-of date (YYYY-MM-DD)")
    pit_parser.add_argument("--hist-start", help="History start date (default: 2y before asof)")
    pit_parser.add_argument("--profile", default="Balanced", help="Profile (Balanced/Growth/Value/Momentum)")
    pit_parser.add_argument("--use-forecasts", action="store_true", help="Enable forecast signals (default: off)")
    pit_parser.add_argument("--json", action="store_true", help="Output full JSON result")

    # walk-forward command
    wf_parser = subparsers.add_parser("walk-forward", help="Run walk-forward replay")
    wf_parser.add_argument("ticker", help="Stock ticker (e.g. AAPL)")
    wf_parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    wf_parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    wf_parser.add_argument("--rebalance-days", type=int, default=20, help="Rebalance frequency (trading days)")
    wf_parser.add_argument("--profile", default="Balanced", help="Profile (Balanced/Growth/Value/Momentum)")
    wf_parser.add_argument("--use-forecasts", action="store_true", help="Enable forecast signals (default: off)")
    wf_parser.add_argument("--no-realized", action="store_true", help="Skip realized returns computation")
    wf_parser.add_argument(
        "--realized-horizons",
        type=int,
        nargs="+",
        default=[5, 20],
        help="Realized return horizons (trading days)",
    )
    wf_parser.add_argument("--verbose", action="store_true", help="Print detailed step results")
    wf_parser.add_argument("--json", action="store_true", help="Output full JSON result")

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Run no-lookahead static audit")
    audit_parser.add_argument("--paths", nargs="+", help="Paths to scan (default: scripts/)")
    audit_parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    if args.command == "pit-score":
        return cmd_pit_score(args)
    elif args.command == "walk-forward":
        return cmd_walk_forward(args)
    elif args.command == "audit":
        return cmd_audit(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
