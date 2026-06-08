"""
Core backtesting engine: walk-forward replay + simple trade simulation.

Phase 2 focus.
Reuses the existing analysis pipeline (calculate_pillars, MC, quant analyst, etc.)
once data compatibility (Phase 1) is in place.

Design: event / date loop for clarity (easy to add stops, rebalances, etc.).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Any, List, Callable, Optional
import pandas as pd

from .data import load_historical_data, asof_snapshot, get_price_series
from .metrics import compute_metrics
from .policy import default_policy, TradeSignal

@dataclass
class BacktestResult:
    ticker: str
    start: str
    end: str
    equity_curve: pd.DataFrame  # date, equity, returns, drawdown, position etc.
    trades: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    final_equity: float
    # TODO: per-date signals/conviction snapshots for debugging


class Backtester:
    """
    Main entry for running historical backtests of the agent.

    Example (future):
        bt = Backtester(ticker="AAPL", start="2023-01-01", profile="Balanced")
        result = bt.run()
    """

    def __init__(
        self,
        ticker: str,
        start: str | date,
        end: str | date | None = None,
        initial_capital: float = 100_000.0,
        profile: str = "Balanced",
        risk_per_trade: float = 0.01,  # 1% risk example
        rebalance_days: int = 5,  # e.g. weekly-ish
        fast_mode: bool = False,
        # policy: Optional[Callable] = None,
    ):
        self.ticker = ticker.upper()
        self.start = str(start)
        self.end = str(end) if end else str(date.today())
        self.initial_capital = initial_capital
        self.profile = profile
        self.risk_per_trade = risk_per_trade
        self.rebalance_days = rebalance_days
        self.fast_mode = fast_mode
        # self.policy = policy or default_policy

        self._data: Optional[Dict[str, Any]] = None

    def _prepare_data(self):
        if self._data is None:
            self._data = load_historical_data(self.ticker, self.start, self.end)
        return self._data

    def run(self) -> BacktestResult:
        """
        Execute the walk-forward backtest.
        MVP: simple loop over rebalance dates, call (future) policy, naive simulator.
        """
        data = self._prepare_data()
        hist = data["history"]
        price_series = get_price_series(hist)

        # Generate candidate rebalance dates (business days in range)
        dates = pd.bdate_range(start=self.start, end=self.end, freq=f"{self.rebalance_days}B")
        if len(dates) == 0:
            dates = [pd.Timestamp(self.start)]

        equity = self.initial_capital
        cash = self.initial_capital
        position = 0.0  # shares
        entry_price = 0.0
        trades: List[Dict[str, Any]] = []
        equity_records = []

        for ts in dates:
            asof = ts.date()
            try:
                snap = asof_snapshot(data, asof)
            except Exception:
                continue

            current_price = float(price_series.loc[:str(asof)].iloc[-1].item() if hasattr(price_series.loc[:str(asof)].iloc[-1], "item") else price_series.loc[:str(asof)].iloc[-1])

            # Build replay data dict for pillars (mimics fetch_stock_data output)
            replay_data = {
                "ticker": self.ticker,
                "info": snap.get("info", {}),
                "history": snap.get("history"),
                "current_price": current_price,
            }
            hist_slice = snap.get("history")

            # Full pillars with replay support (bt-04)
            try:
                from score import calculate_pillars
                dyn = not self.fast_mode
                if self.fast_mode:
                    # Stub heavy GPU signals for fast backtests (price/stat signals still run with hist)
                    import score as _score_mod
                    orig_calc = _score_mod.calculate_pillars
                    def _fast_calc(data, profile="Balanced", compute_dynamic_weights=False, hist=None, asof=None):
                        # Temporarily disable GPU prints/runs by patching inside, but for simplicity run and accept
                        # For true fast, user can edit or we can add flag to calculate_pillars later
                        return orig_calc(data, profile, compute_dynamic_weights=False, hist=hist, asof=asof)
                    scores = _fast_calc(replay_data, self.profile, dyn, hist=hist_slice, asof=str(asof))
                else:
                    scores = calculate_pillars(replay_data, self.profile, compute_dynamic_weights=dyn, hist=hist_slice, asof=str(asof))
            except Exception as e:
                scores = {"overall": 50.0, "signals": {}, "error": str(e)[:100]}

            # Quant analyst (uses updated signals where possible)
            quant_out = {}
            try:
                from agents.quantitative_analyst.quantitative_analyst import create_quantitative_analyst
                quant_node = create_quantitative_analyst()
                q_state = {"ticker": self.ticker, "company_of_interest": self.ticker, "messages": []}
                quant_out = quant_node(q_state)
            except Exception as e:
                quant_out = {"quantitative_conviction": "Medium", "error": str(e)[:80]}

            # Real policy decision (bt-06)
            sig = default_policy(
                scores,
                quant_output=quant_out,
                current_price=current_price,
                atr_pct=float( (scores.get("signals", {}).get("atr_vol", {}) or {}).get("atr_percent", 0) ),
                mc_risk=scores.get("signals", {}).get("mc_risk"),
                profile=self.profile,
            )
            action = sig.action
            size = 0.0
            stop = sig.stop_price
            target = sig.target_price

            # For simulator visibility
            mom = scores.get("signals", {}).get("momentum", {})
            atr = scores.get("signals", {}).get("atr_vol", {})
            mcr = scores.get("signals", {}).get("mc_risk", {})

            # Simple simulator (basic long entry on policy signal, mark-to-market; stops/ exits in next iterations)
            if action == "long" and position == 0 and cash > 0:
                risk_amt = cash * self.risk_per_trade
                # crude size using ATR if available
                atr_val = float(atr.get("atr_percent", 2.0) or 2.0)
                risk_per_share = max(current_price * 0.01, current_price * (atr_val / 100) * 1.5)
                shares = max(1, int(risk_amt / risk_per_share))
                position = shares
                entry_price = current_price
                cash -= shares * current_price
                trades.append({
                    "entry_date": str(asof),
                    "entry_price": entry_price,
                    "shares": shares,
                    "action": "long",
                    "conviction": sig.conviction,
                    "score": overall if 'overall' in locals() else scores.get("overall"),
                })

            # Very basic stop logic (if we have stop and price below)
            if position > 0 and stop and current_price < float(stop):
                cash += position * current_price
                if trades:
                    trades[-1]["exit_date"] = str(asof)
                    trades[-1]["exit_price"] = current_price
                    trades[-1]["pnl"] = (current_price - entry_price) * position
                position = 0

            # Mark to market
            mtm_equity = cash + position * current_price
            equity_records.append({
                "date": str(asof),
                "equity": mtm_equity,
                "price": current_price,
                "position": position,
                "conviction": getattr(sig, 'conviction', None) if 'sig' in locals() else None,
                "action": getattr(sig, 'action', None) if 'sig' in locals() else action,
            })

        eq_df = pd.DataFrame(equity_records)
        if not eq_df.empty:
            eq_df["date"] = pd.to_datetime(eq_df["date"])
            eq_df = eq_df.set_index("date")
            eq_df["returns"] = eq_df["equity"].pct_change().fillna(0)
            eq_df["cum_returns"] = (1 + eq_df["returns"]).cumprod() - 1
            # TODO: drawdown calc

        # Use metrics (Phase 3 progress)
        metrics = compute_metrics(eq_df, trades)

        return BacktestResult(
            ticker=self.ticker,
            start=self.start,
            end=self.end,
            equity_curve=eq_df,
            trades=trades,
            metrics=metrics,
            final_equity=float(eq_df["equity"].iloc[-1]) if not eq_df.empty else self.initial_capital,
        )


# TODO (bt-05+): Add support for stop/target simulation using subsequent bars,
# cost model, multi-position, etc.
# TODO: integrate real call to calculate_pillars + quant analyst once Phase 1 data layer done.
