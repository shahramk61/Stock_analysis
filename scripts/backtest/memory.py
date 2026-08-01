"""
Walk-forward-safe decision memory (Abzu-inspired episodic journal).

Rules:
- Only past-available facts are exposed via asof(day).
- Closed-trade PnL is available only when exit_date <= asof.
- Open position state is execution memory (known at asof).
- Ingestion/proposals under journal/rules/pending/ are NOT ground truth.

Memory does not invent metrics; it only stores what the engine already recorded.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


def _d(s: str | None) -> str:
    if not s:
        return ""
    return str(s)[:10]


def _le(a: str, b: str) -> bool:
    """True if date a <= date b (YYYY-MM-DD)."""
    return _d(a) <= _d(b) if a and b else False


@dataclass
class MemoryConfig:
    """Procedural rules (current authority). Promote changes only with evidence."""
    lookback_decisions: int = 10
    lookback_trades: int = 5
    stop_cooldown_days: int = 5          # no new long for N calendar days after stop
    loss_streak_size_cut: int = 2        # after N consecutive losses, cut size
    loss_streak_risk_mult: float = 0.5
    post_stop_risk_mult: float = 0.5     # while in cooldown
    enabled: bool = True


@dataclass
class DecisionMemory:
    """In-run + optional disk journal of decisions and closed trades."""

    ticker: str = ""
    config: MemoryConfig = field(default_factory=MemoryConfig)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    # snapshots taken at each decision asof (for export / audit)
    snapshots: List[Dict[str, Any]] = field(default_factory=list)

    def record_decision(self, decision: Dict[str, Any]) -> None:
        self.decisions.append(deepcopy(decision))

    def record_trade(self, trade: Dict[str, Any]) -> None:
        self.trades.append(deepcopy(trade))

    def update_last_trade(self, **fields: Any) -> None:
        if self.trades:
            self.trades[-1].update(fields)

    def closed_trades_asof(self, asof: str) -> List[Dict[str, Any]]:
        """Trades with exit_date set and exit_date <= asof (realized only)."""
        out = []
        for t in self.trades:
            ex = t.get("exit_date")
            if ex and _le(str(ex), asof):
                out.append(t)
        return out

    def open_trade_asof(self, asof: str) -> Optional[Dict[str, Any]]:
        """Most recent trade still open as of asof (entry <= asof, no exit yet or exit > asof)."""
        open_t = None
        for t in self.trades:
            ent = t.get("entry_date")
            if not ent or not _le(str(ent), asof):
                continue
            ex = t.get("exit_date")
            if not ex or not _le(str(ex), asof):
                # not yet exited as of asof
                open_t = t
        return open_t

    def decisions_asof(self, asof: str) -> List[Dict[str, Any]]:
        return [d for d in self.decisions if d.get("date") and _le(str(d["date"]), asof)]

    def last_stop_exit_asof(self, asof: str) -> Optional[Dict[str, Any]]:
        closed = self.closed_trades_asof(asof)
        for t in reversed(closed):
            if str(t.get("exit_reason", "")).lower() == "stop":
                return t
        return None

    def consecutive_losses_asof(self, asof: str) -> int:
        closed = self.closed_trades_asof(asof)
        n = 0
        for t in reversed(closed):
            pnl = t.get("pnl")
            if pnl is None:
                break
            if float(pnl) < 0:
                n += 1
            else:
                break
        return n

    def days_since(self, earlier: str, asof: str) -> int:
        try:
            a = datetime.strptime(_d(earlier), "%Y-%m-%d")
            b = datetime.strptime(_d(asof), "%Y-%m-%d")
            return max(0, (b - a).days)
        except Exception:
            return 999

    def snapshot_asof(
        self,
        asof: str,
        *,
        position: float = 0.0,
        entry_price: float = 0.0,
        stop_price: Optional[float] = None,
        current_price: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Structured memory visible on decision day `asof`.
        No future decisions or unrealized-as-closed PnL leaks.
        """
        cfg = self.config
        past_dec = self.decisions_asof(asof)[-cfg.lookback_decisions :]
        closed = self.closed_trades_asof(asof)[-cfg.lookback_trades :]
        last_stop = self.last_stop_exit_asof(asof)
        loss_streak = self.consecutive_losses_asof(asof)

        cooldown_active = False
        cooldown_remaining = 0
        if last_stop and last_stop.get("exit_date"):
            elapsed = self.days_since(str(last_stop["exit_date"]), asof)
            if elapsed < cfg.stop_cooldown_days:
                cooldown_active = True
                cooldown_remaining = cfg.stop_cooldown_days - elapsed

        unrealized = None
        if position > 0 and entry_price > 0 and current_price > 0:
            unrealized = round((current_price - entry_price) * position, 4)

        risk_mult = 1.0
        flags: List[str] = []
        if cooldown_active:
            risk_mult *= cfg.post_stop_risk_mult
            flags.append(f"stop_cooldown({cooldown_remaining}d left)")
        if loss_streak >= cfg.loss_streak_size_cut:
            risk_mult *= cfg.loss_streak_risk_mult
            flags.append(f"loss_streak={loss_streak}")

        snap = {
            "asof": _d(asof),
            "ticker": self.ticker,
            "authority": "episodic",  # not promoted policy doctrine
            "recent_decisions": [
                {
                    "date": d.get("date"),
                    "action": d.get("action"),
                    "overall_score": d.get("overall_score"),
                    "conviction": d.get("conviction"),
                    "rationale": (d.get("rationale") or "")[:160],
                }
                for d in past_dec
            ],
            "closed_trades": [
                {
                    "entry_date": t.get("entry_date"),
                    "exit_date": t.get("exit_date"),
                    "exit_reason": t.get("exit_reason"),
                    "pnl": t.get("pnl"),
                    "score": t.get("score"),
                    "conviction": t.get("conviction"),
                }
                for t in closed
            ],
            "open_position": {
                "shares": position,
                "entry_price": entry_price if position > 0 else None,
                "stop_price": stop_price if position > 0 else None,
                "unrealized_pnl": unrealized,
            }
            if position > 0
            else None,
            "last_stop": {
                "exit_date": last_stop.get("exit_date"),
                "pnl": last_stop.get("pnl"),
                "score": last_stop.get("score"),
            }
            if last_stop
            else None,
            "loss_streak": loss_streak,
            "stop_cooldown_active": cooldown_active,
            "stop_cooldown_remaining_days": cooldown_remaining,
            "risk_multiplier": round(risk_mult, 4),
            "flags": flags,
            "config": {
                "stop_cooldown_days": cfg.stop_cooldown_days,
                "loss_streak_size_cut": cfg.loss_streak_size_cut,
                "enabled": cfg.enabled,
            },
        }
        return snap

    def summary_text(self, snap: Dict[str, Any]) -> str:
        """Human-readable block for quant debate / prompts (facts only)."""
        lines = [
            f"[Decision Memory asof {snap.get('asof')}] ticker={snap.get('ticker')}",
        ]
        flags = snap.get("flags") or []
        if flags:
            lines.append("Active flags: " + ", ".join(flags))
        else:
            lines.append("Active flags: none")
        lines.append(f"Risk multiplier from memory: {snap.get('risk_multiplier', 1.0)}")

        op = snap.get("open_position")
        if op:
            lines.append(
                f"Open position: {op.get('shares')} sh @ {op.get('entry_price')}, "
                f"stop={op.get('stop_price')}, unrealized={op.get('unrealized_pnl')}"
            )
        else:
            lines.append("Open position: none")

        ls = snap.get("last_stop")
        if ls:
            lines.append(
                f"Last stop-out: exit {ls.get('exit_date')} pnl={ls.get('pnl')} "
                f"(entry score was {ls.get('score')})"
            )

        closed = snap.get("closed_trades") or []
        if closed:
            lines.append(f"Recent closed trades ({len(closed)}):")
            for t in closed[-3:]:
                lines.append(
                    f"  - {t.get('entry_date')}→{t.get('exit_date')} "
                    f"{t.get('exit_reason')} pnl={t.get('pnl')}"
                )

        decs = snap.get("recent_decisions") or []
        if decs:
            last = decs[-1]
            lines.append(
                f"Last decision: {last.get('date')} action={last.get('action')} "
                f"score={last.get('overall_score')} conv={last.get('conviction')}"
            )
        return "\n".join(lines)

    def apply_to_policy_inputs(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        """Compact dict for default_policy memory= kwarg."""
        return {
            "risk_multiplier": float(snap.get("risk_multiplier") or 1.0),
            "block_new_long": bool(snap.get("stop_cooldown_active")),
            "flags": list(snap.get("flags") or []),
            "loss_streak": int(snap.get("loss_streak") or 0),
            "stop_cooldown_active": bool(snap.get("stop_cooldown_active")),
            "summary": self.summary_text(snap),
        }

    def store_snapshot(self, snap: Dict[str, Any]) -> None:
        self.snapshots.append(deepcopy(snap))

    def to_export(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "config": asdict(self.config),
            "decisions": self.decisions,
            "trades": self.trades,
            "snapshots": self.snapshots,
            "authority_note": (
                "Episodic run memory. Procedural rules live in MemoryConfig / "
                "journal/rules/current/. Pending proposals are not ground truth."
            ),
        }

    def save_journal_run(
        self,
        repo_root: str,
        *,
        start: str,
        end: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Persist this run under journal/runs/ (episodic).
        Does NOT promote policy rules — that requires journal/rules/pending + human/gates.
        """
        runs_dir = os.path.join(repo_root, "journal", "runs")
        os.makedirs(runs_dir, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(runs_dir, f"{self.ticker}_{start}_{end}_{stamp}.json")
        payload = self.to_export()
        payload["run_meta"] = {
            "start": start,
            "end": end,
            "saved_at": stamp,
            "metrics": metrics or {},
            "authority": "episodic",
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        return path


def load_prior_journal(
    repo_root: str,
    ticker: str,
    asof: str,
) -> List[Dict[str, Any]]:
    """
    Load closed trades from prior journal runs with exit_date <= asof.
    For cross-run episodic memory (optional). Safe if no files.
    """
    runs_dir = os.path.join(repo_root, "journal", "runs")
    if not os.path.isdir(runs_dir):
        return []
    closed: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(runs_dir)):
        if not name.startswith(ticker.upper()) or not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(runs_dir, name)) as f:
                data = json.load(f)
            for t in data.get("trades") or []:
                ex = t.get("exit_date")
                if ex and _le(str(ex), asof):
                    closed.append(t)
        except Exception:
            continue
    return closed
