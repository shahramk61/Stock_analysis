"""
Performance metrics for backtest results.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def compute_metrics(
    equity_curve: pd.DataFrame,
    trades: list,
    benchmark_returns: pd.Series | None = None,
    initial_capital: Optional[float] = None,
) -> Dict[str, Any]:
    """
    equity_curve: DataFrame with 'equity' (and optional 'returns'), DatetimeIndex.
    total_return is always vs initial_capital when provided (not first equity point).
    """
    if equity_curve is None or equity_curve.empty:
        return {"note": "no data"}

    eq = equity_curve["equity"].astype(float)
    start_cap = float(initial_capital) if initial_capital and initial_capital > 0 else float(eq.iloc[0])
    end_eq = float(eq.iloc[-1])

    total_return = (end_eq / start_cap) - 1.0 if start_cap > 0 else 0.0
    days = max((eq.index[-1] - eq.index[0]).days, 1)
    years = days / 365.25
    cagr = (end_eq / start_cap) ** (1 / years) - 1 if years > 0 and start_cap > 0 else 0.0

    if "returns" in equity_curve.columns:
        rets = equity_curve["returns"].astype(float).fillna(0.0)
    else:
        rets = eq.pct_change().fillna(0.0)
        if start_cap > 0:
            rets.iloc[0] = eq.iloc[0] / start_cap - 1.0

    vol = float(rets.std() * np.sqrt(252)) if len(rets) > 1 else 0.0
    sharpe = float((rets.mean() * 252) / vol) if vol > 0 else 0.0

    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max.replace(0, np.nan)
    max_dd = float(dd.min()) if len(dd) else 0.0

    pnls = [float(t.get("pnl", 0.0)) for t in trades if t.get("pnl") is not None]
    if pnls:
        wins = [p for p in pnls if p > 0]
        win_rate = len(wins) / len(pnls)
        expectancy = float(np.mean(pnls))
    else:
        win_rate = 0.0
        expectancy = 0.0

    metrics: Dict[str, Any] = {
        "initial_capital": round(start_cap, 2),
        "final_equity": round(end_eq, 2),
        "total_return": round(total_return * 100, 2),
        "cagr": round(cagr * 100, 2),
        "volatility_ann": round(vol * 100, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd * 100, 2),
        "win_rate": round(win_rate * 100, 1),
        "expectancy_per_trade": round(expectancy, 2),
        "num_trades": len(trades),
        "num_closed_trades": len(pnls),
    }

    if benchmark_returns is not None and not benchmark_returns.empty:
        bench = benchmark_returns.reindex(rets.index).fillna(0)
        excess = rets - bench
        metrics["bench_cagr"] = (
            round(((1 + bench).prod() ** (1 / years) - 1) * 100, 2) if years > 0 else 0
        )
        ex_vol = float(excess.std() * np.sqrt(252)) or 1.0
        metrics["excess_sharpe"] = round(float(excess.mean() * 252) / ex_vol, 3)

    return metrics


def summarize(result: "BacktestResult") -> str:  # type: ignore
    m = result.metrics
    return (
        f"{result.ticker} {result.start}→{result.end} | "
        f"Final ${result.final_equity:,.0f} | "
        f"CAGR {m.get('cagr', 0):.1f}% | Sharpe {m.get('sharpe', 0):.2f} | "
        f"MaxDD {m.get('max_drawdown', 0):.1f}% | Trades {m.get('num_trades', 0)}"
    )
