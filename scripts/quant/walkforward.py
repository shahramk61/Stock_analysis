"""
Walk-forward replay for Quant measurement.

Steps asof forward across a date range, computing PIT scores at each rebalance.
Records score evolution and optionally attaches realized returns for falsification.
"""

import pandas as pd
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from scripts.quant.pit_score import compute_pit_score
from scripts.quant.no_lookahead import lookahead_guard


def run_walkforward(
    ticker: str,
    start: str | date,
    end: str | date,
    hist: Optional[pd.DataFrame] = None,
    rebalance_days: int = 20,
    profile: str = "Balanced",
    use_forecasts: bool = False,
    attach_realized_returns: bool = True,
    realized_horizons: List[int] = None,
) -> Dict[str, Any]:
    """
    Walk-forward replay: compute PIT scores at each rebalance point.

    Args:
        ticker: Stock ticker symbol
        start: Start date for replay (YYYY-MM-DD or date)
        end: End date for replay (YYYY-MM-DD or date)
        hist: Full OHLCV history (must cover start - warmup to end + max realized horizon)
        rebalance_days: Number of trading days between rebalances
        profile: Scoring profile
        use_forecasts: Whether to enable forecast signals (default False)
        attach_realized_returns: Whether to compute realized returns after each asof
        realized_horizons: List of forward horizons (trading days) for realized returns

    Returns:
        Dictionary with:
        - ticker: Ticker symbol
        - start: Start date
        - end: End date
        - rebalance_days: Rebalance frequency
        - steps: List of step dicts (asof, score, availability, realized_returns)
        - summary: Aggregate statistics
    """
    if isinstance(start, str):
        start_dt = pd.Timestamp(start).date()
    else:
        start_dt = start

    if isinstance(end, str):
        end_dt = pd.Timestamp(end).date()
    else:
        end_dt = end

    if realized_horizons is None:
        realized_horizons = [5, 20]  # Default: 5-day and 20-day forward returns

    if hist is None:
        raise ValueError(
            "Walk-forward replay requires pre-loaded hist covering the full range + warmup + realized horizons."
        )

    if not isinstance(hist.index, pd.DatetimeIndex):
        hist.index = pd.to_datetime(hist.index)

    # Get trading days in the range
    range_hist = hist.loc[start_dt:end_dt]
    if range_hist.empty:
        return {
            "error": f"No trading days found for {ticker} between {start_dt} and {end_dt}",
            "ticker": ticker,
            "start": str(start_dt),
            "end": str(end_dt),
        }

    trading_days = range_hist.index
    rebalance_dates = trading_days[::rebalance_days]

    steps = []

    # Run with lookahead guard enabled
    with lookahead_guard():
        for asof_ts in rebalance_dates:
            asof_date = asof_ts.date()
            asof_str = str(asof_date)

            # Slice hist to asof
            hist_asof = hist.loc[:asof_ts].copy()

            # Compute PIT score
            try:
                score_result = compute_pit_score(
                    ticker=ticker,
                    asof=asof_date,
                    hist=hist_asof,
                    profile=profile,
                    use_forecasts=use_forecasts,
                )
            except Exception as e:
                score_result = {
                    "error": str(e),
                    "ticker": ticker,
                    "asof": asof_str,
                }

            # Attach realized returns (computed AFTER asof from future bars)
            realized = {}
            if attach_realized_returns and "error" not in score_result:
                try:
                    asof_close = float(hist_asof["Close"].iloc[-1])
                    for horizon in realized_horizons:
                        # Find the trading day `horizon` days after asof
                        future_idx = trading_days[trading_days > asof_ts]
                        if len(future_idx) > horizon - 1:
                            future_date = future_idx[horizon - 1]
                            if future_date in hist.index:
                                future_close = float(hist.loc[future_date, "Close"])
                                realized_return = (future_close / asof_close - 1) * 100
                                realized[f"{horizon}d"] = {
                                    "return_pct": round(realized_return, 2),
                                    "future_date": str(future_date.date()),
                                    "asof_close": round(asof_close, 2),
                                    "future_close": round(future_close, 2),
                                }
                except Exception:
                    pass

            step = {
                "asof": asof_str,
                "score": score_result.get("overall_score"),
                "pillar_scores": score_result.get("pillar_scores"),
                "last_print": score_result.get("last_print"),
                "last_print_date": score_result.get("last_print_date"),
                "last_print_source": score_result.get("last_print_source"),
                "availability": score_result.get("availability"),
                "signals": score_result.get("signals"),  # Contains mc_risk with cvar_95
                "realized_returns": realized if realized else None,
                # Note: decision_memory/memory_text requires journal integration
                # For now, each step is stateless (no cross-step memory)
                # To add memory: load journal as of each asof, compute snapshot
            }
            steps.append(step)

    # Summary statistics
    valid_scores = [s["score"] for s in steps if s["score"] is not None]
    summary = {
        "num_steps": len(steps),
        "num_valid_scores": len(valid_scores),
        "avg_score": round(sum(valid_scores) / len(valid_scores), 1)
        if valid_scores
        else None,
        "min_score": round(min(valid_scores), 1) if valid_scores else None,
        "max_score": round(max(valid_scores), 1) if valid_scores else None,
    }

    return {
        "ticker": ticker,
        "start": str(start_dt),
        "end": str(end_dt),
        "rebalance_days": rebalance_days,
        "profile": profile,
        "use_forecasts": use_forecasts,
        "steps": steps,
        "summary": summary,
    }
