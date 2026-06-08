"""
Performance metrics for backtest results.

Pure pandas/numpy implementation to stay lightweight (no heavy optional deps for MVP).
Covers standard stats + benchmark comparison.

See plan Phase 3.
"""

from __future__ import annotations
from typing import Dict, Any
import pandas as pd
import numpy as np


def compute_metrics(equity_curve: pd.DataFrame, trades: list, benchmark_returns: pd.Series | None = None) -> Dict[str, Any]:
    """
    equity_curve: DataFrame with 'equity', 'returns' (daily), index datetime.
    trades: list of dicts with at least 'pnl' or entry/exit.
    """
    if equity_curve.empty:
        return {"note": "no data"}

    eq = equity_curve["equity"]
    rets = equity_curve.get("returns", eq.pct_change().fillna(0))

    total_return = (eq.iloc[-1] / eq.iloc[0]) - 1
    days = (eq.index[-1] - eq.index[0]).days or 1
    years = days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0

    vol = rets.std() * np.sqrt(252)
    sharpe = (rets.mean() * 252) / vol if vol > 0 else 0.0

    # Max drawdown
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    max_dd = dd.min()

    # Simple trade stats
    if trades:
        pnls = [t.get("pnl", 0.0) for t in trades if "pnl" in t]
        wins = [p for p in pnls if p > 0]
        win_rate = len(wins) / len(pnls) if pnls else 0.0
        expectancy = np.mean(pnls) if pnls else 0.0
    else:
        win_rate = 0.0
        expectancy = 0.0

    metrics = {
        "total_return": round(total_return * 100, 2),
        "cagr": round(cagr * 100, 2),
        "volatility_ann": round(vol * 100, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd * 100, 2),
        "win_rate": round(win_rate * 100, 1),
        "expectancy_per_trade": round(expectancy, 2),
        "num_trades": len(trades),
    }

    if benchmark_returns is not None and not benchmark_returns.empty:
        # Align and compute simple excess / info
        bench = benchmark_returns.reindex(rets.index).fillna(0)
        excess = rets - bench
        metrics["bench_cagr"] = round(((1 + bench).prod() ** (1 / years) - 1) * 100, 2) if years > 0 else 0
        metrics["excess_sharpe"] = round((excess.mean() * 252) / (excess.std() * np.sqrt(252) or 1), 3)

    return metrics


def summarize(result: "BacktestResult") -> str:  # type: ignore
    """Human readable one-liner + key numbers."""
    m = result.metrics
    return (
        f"{result.ticker} {result.start}→{result.end} | "
        f"Final ${result.final_equity:,.0f} | "
        f"CAGR {m.get('cagr',0):.1f}% | Sharpe {m.get('sharpe',0):.2f} | "
        f"MaxDD {m.get('max_drawdown',0):.1f}% | Trades {m.get('num_trades',0)}"
    )
