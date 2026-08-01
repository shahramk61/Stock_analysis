"""
Walk-forward backtest engine for the Stock Analysis agent.

Execution model (realistic enough for validation):
1. On decision days: compute signals/scores using data ≤ decision close.
2. Orders fill on the *next* trading day's open (next-bar fill, not same-close).
3. While in a position: check stop using the day's low (gap-aware: fill at open if gapped through).
4. Policy `flat` closes the position on next open.
5. Equity marked daily at close; returns vs initial capital; BH uses test window only.

No demo/relaxed forced re-entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from .data import (
    load_historical_data,
    asof_snapshot,
    get_price_series,
    trading_days_in_range,
    next_trading_day,
    bar_on,
)
from .metrics import compute_metrics
from .policy import default_policy, position_size_shares
from .memory import DecisionMemory, MemoryConfig


COMMISSION_PCT = 0.001   # 0.1% round-trip total → half per side
SLIPPAGE_PCT = 0.0005    # 0.05% one-way
MAX_GROSS_EXPOSURE = 0.95  # never deploy more than 95% of cash notional


@dataclass
class BacktestResult:
    ticker: str
    start: str
    end: str
    equity_curve: pd.DataFrame
    trades: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    final_equity: float
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    memory_export: Optional[Dict[str, Any]] = None


class Backtester:
    def __init__(
        self,
        ticker: str,
        start: str | date,
        end: str | date | None = None,
        initial_capital: float = 100_000.0,
        profile: str = "Balanced",
        risk_per_trade: float = 0.01,
        rebalance_days: int = 5,
        fast_mode: bool = False,
        debate_mode: bool = False,
        x_pre_fetched: dict | None = None,
        relaxed: bool = False,  # kept for API compat; ignored (strict execution only)
        use_forecasts: bool = True,
        use_memory: bool = True,
        memory_config: Optional[MemoryConfig] = None,
    ):
        self.ticker = ticker.upper()
        self.start = str(start)
        self.end = str(end) if end else str(date.today())
        self.initial_capital = float(initial_capital)
        self.profile = profile
        self.risk_per_trade = risk_per_trade
        self.rebalance_days = max(1, int(rebalance_days))
        self.fast_mode = fast_mode
        self.debate_mode = debate_mode
        self.x_pre_fetched = x_pre_fetched
        self.relaxed = False  # demo mode disabled
        self.use_forecasts = use_forecasts
        self.use_memory = use_memory
        self.memory_config = memory_config or MemoryConfig(enabled=use_memory)
        self._data: Optional[Dict[str, Any]] = None

    def _prepare_data(self) -> Dict[str, Any]:
        if self._data is None:
            self._data = load_historical_data(self.ticker, self.start, self.end)
        return self._data

    def _close_position(
        self,
        cash: float,
        position: float,
        entry_price: float,
        fill_price: float,
        fill_date: str,
        trades: List[Dict[str, Any]],
        reason: str,
        memory: Optional[DecisionMemory] = None,
    ) -> tuple[float, float, float]:
        """Close full long; returns (cash, position=0, entry_price=0)."""
        if position <= 0:
            return cash, 0.0, 0.0
        exit_cost = position * fill_price * (COMMISSION_PCT / 2 + SLIPPAGE_PCT)
        proceeds = position * fill_price - exit_cost
        cash = cash + proceeds
        if trades:
            t = trades[-1]
            if "exit_date" not in t:
                t["exit_date"] = fill_date
                t["exit_price"] = round(float(fill_price), 4)
                t["exit_cost"] = round(exit_cost, 4)
                t["exit_reason"] = reason
                gross = (fill_price - entry_price) * position
                t["pnl"] = round(gross - t.get("entry_cost", 0) - exit_cost, 4)
                if memory is not None:
                    memory.update_last_trade(
                        exit_date=t["exit_date"],
                        exit_price=t["exit_price"],
                        exit_cost=t["exit_cost"],
                        exit_reason=t["exit_reason"],
                        pnl=t["pnl"],
                    )
        return cash, 0.0, 0.0

    def _open_long(
        self,
        cash: float,
        shares: int,
        fill_price: float,
        fill_date: str,
        stop: Optional[float],
        sig_meta: Dict[str, Any],
        trades: List[Dict[str, Any]],
        memory: Optional[DecisionMemory] = None,
    ) -> tuple[float, float, float, Optional[float]]:
        """Open long; returns (cash, position, entry_price, stop)."""
        if shares <= 0 or cash <= 0:
            return cash, 0.0, 0.0, None
        notional = shares * fill_price
        entry_cost = notional * (COMMISSION_PCT / 2 + SLIPPAGE_PCT)
        total = notional + entry_cost
        if total > cash:
            shares = int(cash / (fill_price * (1 + COMMISSION_PCT / 2 + SLIPPAGE_PCT)))
            if shares <= 0:
                return cash, 0.0, 0.0, None
            notional = shares * fill_price
            entry_cost = notional * (COMMISSION_PCT / 2 + SLIPPAGE_PCT)
            total = notional + entry_cost
        cash -= total
        rec = {
            "entry_date": fill_date,
            "entry_price": round(float(fill_price), 4),
            "shares": int(shares),
            "action": "long",
            "stop_price": float(stop) if stop else None,
            "conviction": sig_meta.get("conviction"),
            "score": sig_meta.get("score"),
            "rationale": sig_meta.get("rationale"),
            "decision_date": sig_meta.get("decision_date"),
            "entry_cost": round(entry_cost, 4),
        }
        trades.append(rec)
        if memory is not None:
            memory.record_trade(rec)
        return cash, float(shares), float(fill_price), stop

    def run(self) -> BacktestResult:
        data = self._prepare_data()
        hist = data["history"]
        close = get_price_series(hist, "Close")
        open_ = get_price_series(hist, "Open") if "Open" in hist.columns else close
        low = get_price_series(hist, "Low") if "Low" in hist.columns else close
        high = get_price_series(hist, "High") if "High" in hist.columns else close

        days = trading_days_in_range(hist, self.start, self.end)
        if len(days) == 0:
            empty = pd.DataFrame()
            return BacktestResult(
                ticker=self.ticker, start=self.start, end=self.end,
                equity_curve=empty, trades=[], metrics={"note": "no trading days"},
                final_equity=self.initial_capital,
            )

        # Decision schedule: every N-th trading day in window
        decision_dates = set(days[:: self.rebalance_days])

        cash = self.initial_capital
        position = 0.0
        entry_price = 0.0
        stop_price: Optional[float] = None
        trades: List[Dict[str, Any]] = []
        decisions: List[Dict[str, Any]] = []
        equity_records: List[Dict[str, Any]] = []

        mem = DecisionMemory(ticker=self.ticker, config=self.memory_config)
        if not self.use_memory:
            mem.config.enabled = False

        # Pending order filled next open: {"side": "buy"|"sell", "shares", "stop", "meta"}
        pending: Optional[Dict[str, Any]] = None

        for i, day in enumerate(days):
            day_str = str(pd.Timestamp(day).date())
            c = float(close.loc[day]) if day in close.index else float(close.iloc[close.index.get_indexer([day], method="ffill")[0]])
            o = float(open_.loc[day]) if day in open_.index else c
            lo = float(low.loc[day]) if day in low.index else c
            hi = float(high.loc[day]) if day in high.index else c

            # ── 1) Fill pending orders at today's open ───────────────────────
            if pending is not None:
                side = pending["side"]
                if side == "sell" and position > 0:
                    cash, position, entry_price = self._close_position(
                        cash, position, entry_price, o, day_str, trades,
                        pending.get("reason", "signal"), memory=mem,
                    )
                    stop_price = None
                elif side == "buy" and position == 0:
                    cash, position, entry_price, stop_price = self._open_long(
                        cash,
                        int(pending.get("shares", 0)),
                        o,
                        day_str,
                        pending.get("stop"),
                        pending.get("meta") or {},
                        trades,
                        memory=mem,
                    )
                pending = None

            # ── 2) Intraday stop check (long): use low; gap-through → open ───
            if position > 0 and stop_price is not None:
                if lo <= float(stop_price):
                    fill = o if o <= float(stop_price) else float(stop_price)
                    cash, position, entry_price = self._close_position(
                        cash, position, entry_price, fill, day_str, trades, "stop",
                        memory=mem,
                    )
                    stop_price = None

            # ── 3) Decision at close (signals ≤ today) → next-bar order ──────
            decision_note = None
            if day in decision_dates:
                try:
                    snap = asof_snapshot(data, day)
                except Exception:
                    snap = None

                if snap is not None:
                    hist_slice = snap["history"]
                    replay_data = {
                        "ticker": self.ticker,
                        "info": {},
                        "history": hist_slice,
                        "current_price": c,
                    }
                    try:
                        from score import calculate_pillars
                        # Fast mode skips multi-horizon training but keeps FinBERT/news
                        # so sentiment leverage remains available without full ensemble cost.
                        scores = calculate_pillars(
                            replay_data,
                            self.profile,
                            compute_dynamic_weights=not self.fast_mode,
                            hist=hist_slice,
                            asof=day_str,
                            use_gpu_signals=True,
                            use_forecasts=self.use_forecasts and not self.fast_mode,
                        )
                    except Exception as e:
                        scores = {"overall": 50.0, "signals": {}, "error": str(e)[:120]}

                    # Memory snapshot BEFORE this decision (past-only)
                    mem_snap = None
                    mem_policy = None
                    mem_text = ""
                    if self.use_memory and mem.config.enabled:
                        mem_snap = mem.snapshot_asof(
                            day_str,
                            position=position,
                            entry_price=entry_price,
                            stop_price=stop_price,
                            current_price=c,
                        )
                        mem_policy = mem.apply_to_policy_inputs(mem_snap)
                        mem_text = mem_policy.get("summary") or ""
                        mem.store_snapshot(mem_snap)

                    quant_out: Dict[str, Any] = {}
                    try:
                        from agents.quantitative_analyst.quantitative_analyst import (
                            create_quantitative_analyst,
                        )
                        quant_node = create_quantitative_analyst(debate_mode=self.debate_mode)
                        quant_out = quant_node({
                            "ticker": self.ticker,
                            "company_of_interest": self.ticker,
                            "messages": [],
                            "x_sentiment_pre_fetched": self.x_pre_fetched,
                            "use_forecasts": self.use_forecasts and not self.fast_mode,
                            "hist": hist_slice,
                            "asof": day_str,
                            "decision_memory": mem_text,
                            "decision_memory_struct": mem_snap,
                        })
                    except Exception as e:
                        quant_out = {"quantitative_conviction": "Medium", "error": str(e)[:80]}

                    atr_pct = float(
                        (scores.get("signals", {}).get("atr_vol") or {}).get("atr_percent") or 0
                    )
                    sig = default_policy(
                        scores,
                        quant_output=quant_out,
                        current_price=c,
                        atr_pct=atr_pct,
                        mc_risk=(scores.get("signals") or {}).get("mc_risk"),
                        profile=self.profile,
                        relaxed=False,
                        memory=mem_policy,
                    )

                    decision_note = {
                        "date": day_str,
                        "price": c,
                        "overall_score": scores.get("overall"),
                        "action": sig.action,
                        "conviction": sig.conviction,
                        "rationale": sig.rationale,
                        "suggested_risk_pct": sig.suggested_risk_pct,
                        "stop_price": sig.stop_price,
                        "debate_note": quant_out.get("quantitative_debate_commentary") if self.debate_mode else None,
                        "memory_flags": (mem_snap or {}).get("flags") if mem_snap else [],
                        "memory_risk_multiplier": (mem_snap or {}).get("risk_multiplier") if mem_snap else 1.0,
                    }
                    decisions.append(decision_note)
                    mem.record_decision(decision_note)

                    if sig.action == "flat" and position > 0:
                        pending = {"side": "sell", "reason": "flat", "meta": decision_note}
                    elif sig.action == "long" and position == 0:
                        equity_now = cash
                        risk_pct = float(sig.suggested_risk_pct or 0) or float(self.risk_per_trade)
                        shares = position_size_shares(
                            equity=equity_now,
                            risk_pct=risk_pct,
                            price=c,
                            stop_price=sig.stop_price,
                            max_notional_pct=MAX_GROSS_EXPOSURE,
                        )
                        if shares > 0:
                            pending = {
                                "side": "buy",
                                "shares": shares,
                                "stop": sig.stop_price,
                                "meta": {
                                    "conviction": sig.conviction,
                                    "score": scores.get("overall"),
                                    "rationale": sig.rationale,
                                    "decision_date": day_str,
                                },
                            }
                    elif sig.action == "long" and position > 0 and sig.stop_price:
                        if stop_price is None or float(sig.stop_price) > float(stop_price):
                            stop_price = float(sig.stop_price)

            # ── 4) Mark equity at close ──────────────────────────────────────
            mtm = cash + position * c
            equity_records.append({
                "date": day_str,
                "equity": mtm,
                "cash": cash,
                "price": c,
                "position": position,
                "stop": stop_price,
                "overall_score": (decision_note or {}).get("overall_score"),
                "action": (decision_note or {}).get("action"),
                "conviction": (decision_note or {}).get("conviction"),
                "rationale": (decision_note or {}).get("rationale"),
                "debate_note": (decision_note or {}).get("debate_note"),
                "memory_flags": (decision_note or {}).get("memory_flags"),
            })

        # Close any open position at final close (blotter + cash consistency)
        if position > 0 and len(days) > 0:
            last = days[-1]
            last_str = str(pd.Timestamp(last).date())
            last_px = float(close.loc[last]) if last in close.index else float(close.iloc[-1])
            cash, position, entry_price = self._close_position(
                cash, position, entry_price, last_px, last_str, trades, "end_of_backtest",
                memory=mem,
            )
            if equity_records:
                equity_records[-1]["equity"] = cash
                equity_records[-1]["cash"] = cash
                equity_records[-1]["position"] = 0
        eq_df = pd.DataFrame(equity_records)
        if not eq_df.empty:
            eq_df["date"] = pd.to_datetime(eq_df["date"])
            eq_df = eq_df.set_index("date")
            # Returns from initial capital path
            eq_df["returns"] = eq_df["equity"].pct_change()
            eq_df.loc[eq_df.index[0], "returns"] = (
                eq_df["equity"].iloc[0] / self.initial_capital - 1.0
            )
            eq_df["returns"] = eq_df["returns"].fillna(0.0)
            eq_df["cum_returns"] = eq_df["equity"] / self.initial_capital - 1.0
            roll_max = eq_df["equity"].cummax()
            eq_df["drawdown"] = (eq_df["equity"] - roll_max) / roll_max

        metrics = compute_metrics(
            eq_df,
            trades,
            initial_capital=self.initial_capital,
        )

        # Buy & hold over the *test window only* (not warm-up buffer)
        window_close = close.loc[days]
        if len(window_close) >= 2:
            start_px = float(window_close.iloc[0])
            end_px = float(window_close.iloc[-1])
            bh_ret = (end_px / start_px - 1.0) * 100
            metrics["bh_total_return"] = round(bh_ret, 2)
            days_n = max((pd.Timestamp(self.end) - pd.Timestamp(self.start)).days, 1)
            years = days_n / 365.25
            if years > 0 and start_px > 0:
                metrics["bh_cagr"] = round(((end_px / start_px) ** (1 / years) - 1) * 100, 2)
            metrics["vs_bh"] = round(metrics.get("total_return", 0) - bh_ret, 2)
            metrics["bh_start_price"] = round(start_px, 4)
            metrics["bh_end_price"] = round(end_px, 4)

        metrics["num_decisions"] = len(decisions)
        metrics["execution_model"] = "next_open_fill + daily_stop_on_low"
        metrics["fundamentals_pit"] = False
        metrics["memory_enabled"] = bool(self.use_memory and mem.config.enabled)

        final_eq = float(eq_df["equity"].iloc[-1]) if not eq_df.empty else self.initial_capital
        memory_export = mem.to_export() if self.use_memory else None

        return BacktestResult(
            ticker=self.ticker,
            start=self.start,
            end=self.end,
            equity_curve=eq_df,
            trades=trades,
            metrics=metrics,
            final_equity=final_eq,
            decisions=decisions,
            memory_export=memory_export,
        )
