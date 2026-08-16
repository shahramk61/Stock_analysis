"""
CLI for Quant fund tools.

Commands:
  tracker-latest   - Get latest tracker state for tickers at asof date
  tracker-series   - Get tracker time series for tickers over date range
  five-year-model  - Evaluate five-year model for ticker at asof date
  replay-tickets   - Replay PM tickets walk-forward
"""

import json
from datetime import date, datetime

import click
import pandas as pd

from scripts.quant.fund import (
    get_latest_tracker_state,
    get_tracker_time_series,
    evaluate_five_year_model,
    replay_pm_tickets,
    Ticket,
    TicketAction,
)
from scripts.backtest.data import load_historical_data


@click.group()
def cli():
    """Quant fund tools CLI."""
    pass


@cli.command("tracker-latest")
@click.option("--tickers", required=True, help="Comma-separated ticker list (e.g. AAPL,MSFT,GOOGL)")
@click.option("--asof", required=True, help="As-of date (YYYY-MM-DD)")
@click.option("--profile", default="Balanced", help="Scoring profile (default: Balanced)")
@click.option("--output", help="Output file path (JSON)")
def tracker_latest(tickers, asof, profile, output):
    """Get latest tracker state for tickers at asof date."""
    ticker_list = [t.strip() for t in tickers.split(",")]
    
    # Load historical data for all tickers
    click.echo(f"Loading historical data for {len(ticker_list)} tickers...")
    hist_dict = {}
    for ticker in ticker_list:
        try:
            data = load_historical_data(ticker, start="2020-01-01", end=asof)
            hist_dict[ticker] = data["history"]
        except Exception as e:
            click.echo(f"Warning: Could not load data for {ticker}: {e}", err=True)
    
    # Get tracker state
    click.echo(f"Computing tracker state at {asof}...")
    tracker = get_latest_tracker_state(
        tickers=ticker_list,
        asof=asof,
        hist_dict=hist_dict,
        profile=profile,
    )
    
    result = tracker.to_dict()
    
    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
        click.echo(f"Saved to {output}")
    else:
        click.echo(json.dumps(result, indent=2))


@cli.command("tracker-series")
@click.option("--tickers", required=True, help="Comma-separated ticker list")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--rebalance-days", default=20, help="Rebalance frequency (trading days)")
@click.option("--profile", default="Balanced", help="Scoring profile")
@click.option("--output", help="Output file path (JSON)")
def tracker_series(tickers, start, end, rebalance_days, profile, output):
    """Get tracker time series for tickers over date range."""
    ticker_list = [t.strip() for t in tickers.split(",")]
    
    # Load historical data
    click.echo(f"Loading historical data for {len(ticker_list)} tickers...")
    hist_dict = {}
    for ticker in ticker_list:
        try:
            # Load with extra warmup
            warmup_start = (datetime.strptime(start, "%Y-%m-%d") - pd.Timedelta(days=200)).strftime("%Y-%m-%d")
            data = load_historical_data(ticker, start=warmup_start, end=end)
            hist_dict[ticker] = data["history"]
        except Exception as e:
            click.echo(f"Warning: Could not load data for {ticker}: {e}", err=True)
    
    # Get tracker time series
    click.echo(f"Computing tracker time series from {start} to {end}...")
    tracker = get_tracker_time_series(
        tickers=ticker_list,
        start=start,
        end=end,
        hist_dict=hist_dict,
        profile=profile,
        rebalance_days=rebalance_days,
    )
    
    result = tracker.to_dict()
    
    if output:
        with open(output, "w") as f:
            json.dump(result, f, indent=2)
        click.echo(f"Saved to {output}")
    else:
        click.echo(json.dumps(result, indent=2))


@cli.command("five-year-model")
@click.option("--ticker", required=True, help="Ticker symbol")
@click.option("--asof", required=True, help="As-of date (YYYY-MM-DD)")
@click.option("--revenues", help="Historical revenues (comma-separated, oldest first)")
def five_year_model_cmd(ticker, asof, revenues):
    """Evaluate five-year model for ticker at asof date."""
    from scripts.quant.fund.five_year_model import create_pit_fundamentals_stub
    
    if revenues:
        revenue_list = [float(r.strip()) for r in revenues.split(",")]
        pit_fundamentals = create_pit_fundamentals_stub(
            ticker=ticker,
            asof=asof,
            historical_revenues=revenue_list,
        )
    else:
        pit_fundamentals = None
    
    result = evaluate_five_year_model(
        ticker=ticker,
        asof=asof,
        pit_fundamentals=pit_fundamentals,
    )
    
    click.echo(json.dumps(result.to_dict(), indent=2))


@cli.command("replay-tickets")
@click.option("--tickets-file", required=True, help="JSON file with PM tickets")
@click.option("--starting-capital", default=3000.0, help="Starting capital (default: 3000)")
@click.option("--output", help="Output file path (JSON)")
def replay_tickets_cmd(tickets_file, starting_capital, output):
    """Replay PM tickets walk-forward."""
    # Load tickets from file
    with open(tickets_file, "r") as f:
        tickets_data = json.load(f)
    
    # Parse tickets
    tickets = []
    tickers_needed = set()
    for t in tickets_data:
        ticket = Ticket(
            date=datetime.strptime(t["date"], "%Y-%m-%d").date(),
            ticker=t["ticker"],
            action=TicketAction(t["action"]),
            qty=t.get("qty"),
            weight=t.get("weight"),
            limit=t.get("limit"),
        )
        tickets.append(ticket)
        tickers_needed.add(t["ticker"])
    
    # Load historical data for all tickers
    click.echo(f"Loading historical data for {len(tickers_needed)} tickers...")
    hist_dict = {}
    min_date = min(t.date for t in tickets)
    max_date = max(t.date for t in tickets)
    
    for ticker in tickers_needed:
        try:
            warmup_start = (min_date - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
            data = load_historical_data(ticker, start=warmup_start, end=max_date)
            hist_dict[ticker] = data["history"]
        except Exception as e:
            click.echo(f"Warning: Could not load data for {ticker}: {e}", err=True)
    
    # Replay tickets
    click.echo(f"Replaying {len(tickets)} tickets...")
    result = replay_pm_tickets(
        tickets=tickets,
        hist_dict=hist_dict,
        starting_capital=starting_capital,
    )
    
    result_dict = result.to_dict()
    
    if output:
        with open(output, "w") as f:
            json.dump(result_dict, f, indent=2)
        click.echo(f"Saved to {output}")
    else:
        click.echo(json.dumps(result_dict, indent=2))


if __name__ == "__main__":
    cli()
