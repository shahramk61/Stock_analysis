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
        debate_mode: bool = False,
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
        self.debate_mode = debate_mode
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
                use_gpu = not self.fast_mode
                scores = calculate_pillars(replay_data, self.profile, compute_dynamic_weights=dyn,
                                           hist=hist_slice, asof=str(asof), use_gpu_signals=use_gpu)
            except Exception as e:
                scores = {"overall": 50.0, "signals": {}, "error": str(e)[:100]}

            # Quant analyst (uses updated signals where possible)
            quant_out = {}
            try:
                from agents.quantitative_analyst.quantitative_analyst import create_quantitative_analyst
                quant_node = create_quantitative_analyst(debate_mode=self.debate_mode)
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

            debate_note = quant_out.get("quantitative_debate_commentary", "") if self.debate_mode else ""
            quant_report = quant_out.get("quantitative_report", "") if self.debate_mode else ""

            # Simple simulator — this is "paper trading" the agent's decisions
            # We apply a small round-trip cost assumption here so the equity curve
            # is closer to what real trading would feel like.
            COMMISSION_PCT = 0.001   # 0.1% round-trip (tune per broker)
            SLIPPAGE_PCT  = 0.0005   # 0.05% one-way slippage

            if action == "long" and position == 0 and cash > 0:
                risk_amt = cash * self.risk_per_trade
                atr_val = float(atr.get("atr_percent", 2.0) or 2.0)
                risk_per_share = max(current_price * 0.01, current_price * (atr_val / 100) * 1.5)
                shares = max(1, int(risk_amt / risk_per_share))

                # Apply entry costs
                entry_cost = shares * current_price * (COMMISSION_PCT/2 + SLIPPAGE_PCT)
                position = shares
                entry_price = current_price
                cash -= (shares * current_price + entry_cost)

                trades.append({
                    "entry_date": str(asof),
                    "entry_price": entry_price,
                    "shares": shares,
                    "action": "long",
                    "conviction": sig.conviction,
                    "score": overall if 'overall' in locals() else scores.get("overall"),
                    "entry_cost": round(entry_cost, 2),
                })

            # Stop / exit logic with realistic costs
            if position > 0 and stop and current_price < float(stop):
                exit_cost = position * current_price * (COMMISSION_PCT/2 + SLIPPAGE_PCT)
                cash += (position * current_price - exit_cost)
                if trades:
                    trades[-1]["exit_date"] = str(asof)
                    trades[-1]["exit_price"] = current_price
                    gross_pnl = (current_price - entry_price) * position
                    net_pnl = gross_pnl - trades[-1].get("entry_cost", 0) - exit_cost
                    trades[-1]["pnl"] = round(net_pnl, 2)
                    trades[-1]["exit_cost"] = round(exit_cost, 2)
                position = 0

            # Mark to market (unrealized)
            mtm_equity = cash + position * current_price
            equity_records.append({
                "date": str(asof),
                "equity": mtm_equity,
                "price": current_price,
                "position": position,
                "overall_score": scores.get("overall"),
                "conviction": getattr(sig, 'conviction', None) if 'sig' in locals() else None,
                "action": getattr(sig, 'action', None) if 'sig' in locals() else action,
                "rationale": getattr(sig, 'rationale', None) if 'sig' in locals() else None,
                "debate_note": debate_note if debate_note else None,
                "quant_report": quant_report if quant_report else None,
            })

        eq_df = pd.DataFrame(equity_records)
        if not eq_df.empty:
            eq_df["date"] = pd.to_datetime(eq_df["date"])
            eq_df = eq_df.set_index("date")
            eq_df["returns"] = eq_df["equity"].pct_change().fillna(0)
            eq_df["cum_returns"] = (1 + eq_df["returns"]).cumprod() - 1

            # Simple drawdown
            roll_max = eq_df["equity"].cummax()
            eq_df["drawdown"] = (eq_df["equity"] - roll_max) / roll_max

        # Use metrics (Phase 3 progress)
        metrics = compute_metrics(eq_df, trades)

        # Basic buy-and-hold benchmark using the price series we already loaded
        bench_metrics = {}
        if not price_series.empty and len(price_series) > 1:
            start_px = float(price_series.iloc[0].item() if hasattr(price_series.iloc[0], 'item') else price_series.iloc[0])
            end_px = float(price_series.iloc[-1].item() if hasattr(price_series.iloc[-1], 'item') else price_series.iloc[-1])
            bh_return = (end_px / start_px) - 1
            bench_metrics["bh_total_return"] = round(bh_return * 100, 2)
            # rough annualized
            days = (pd.to_datetime(self.end) - pd.to_datetime(self.start)).days or 1
            years = days / 365.25
            if years > 0:
                bench_metrics["bh_cagr"] = round(((end_px / start_px) ** (1 / years) - 1) * 100, 2)
            metrics["vs_bh"] = bench_metrics.get("bh_total_return", 0) - metrics.get("total_return", 0)

        # Attach the raw trades list so callers (CLI, future live runner) can see every executed trade
        # with realistic costs, P&L, conviction, etc. This is the "trade blotter" of the agent.
        result_trades = trades  # will be stored on the BacktestResult below

        # For convenience in the JSON export and live bridge, also keep the final policy signals
        # per rebalance date (the "orders" the agent would have sent to a broker).

        # bt-08: basic no-lookahead note (the hist passed to pillars is strictly sliced <= asof)
        # For stronger validation later: compare scores at D vs what analyze.py would produce on a frozen snapshot of that date.

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
