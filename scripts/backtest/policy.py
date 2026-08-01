"""
Decision policy for the backtesting agent.

Extracts / formalizes rules from current scoring + quant analyst + forecasts
into explicit, configurable, auditable logic that produces TradeSignal.

Phase 2: simple rules first (score + conviction + multi-horizon consensus).
Later: pluggable, risk overlays, optimization guardrails.

See approved plan + NOTES.md (audit of current thresholds).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal


Action = Literal["long", "short", "flat"]


@dataclass
class TradeSignal:
    """Clean, structured output from the agent at a point in time. Ideal for backtest + future execution."""
    ticker: str
    asof: str
    action: Action
    conviction: str  # High/Medium/Low/Unknown (from quant or derived)
    overall_score: float
    suggested_risk_pct: float  # e.g. 0.01 for 1% portfolio risk
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    horizon_days: Optional[int] = None
    rationale: str = ""
    raw_score: Optional[int] = None  # from compute_quant_conviction if available
    # TODO: add source_signals summary, max_position etc.


def default_policy(
    scores: Dict[str, Any],
    quant_output: Optional[Dict[str, Any]] = None,
    current_price: float = 0.0,
    atr_pct: float = 0.0,
    mc_risk: Optional[Dict[str, Any]] = None,
    profile: str = "Balanced",
    relaxed: bool = False,  # deprecated / ignored — strict policy only
    memory: Optional[Dict[str, Any]] = None,
) -> TradeSignal:
    """
    Strict decision policy for backtests / paper trading.

    Uses overall score, multi-horizon consensus, quant conviction, then applies
    hard risk filters (VaR, regime, trend structure) and optional decision memory
    (stop cooldown, loss-streak size cuts). Memory must be walk-forward-safe.
    """
    # `relaxed` is ignored (demo mode removed)
    overall = scores.get("overall", 50.0)
    signals = scores.get("signals", {})
    multi = signals.get("multi_horizon_forecasts") or signals.get("multi_h", {}) or {}
    consensus = multi.get("consensus_direction", "Neutral") if isinstance(multi, dict) else "Neutral"
    consensus_l = str(consensus).lower()

    # Conviction from quant (preferred); soft-adjust from score bands
    q_conv = "Medium"
    q_raw = None
    if quant_output and isinstance(quant_output, dict):
        q_conv = quant_output.get("quantitative_conviction", "Medium") or "Medium"
        qs = quant_output.get("quantitative_signals", {}) or {}
        q_raw = qs.get("raw_conviction_score") if isinstance(qs, dict) else None
    if overall >= 75:
        q_conv = "High"
    elif overall < 45:
        q_conv = "Low"

    # Entry rules (strict)
    if overall >= 70 and "bull" in consensus_l and q_conv in ("High", "Medium"):
        action: Action = "long"
        risk = 0.015 if q_conv == "High" else 0.01
        rationale = f"Score {overall} + Bullish consensus + {q_conv} conviction"
    elif overall >= 60 and q_conv == "High" and "bear" not in consensus_l:
        action = "long"
        risk = 0.01
        rationale = f"Score {overall} + High conviction (no bearish consensus)"
    else:
        action = "flat"
        risk = 0.0
        rationale = f"Score {overall}, {consensus}, {q_conv} → flat"

    # ── Hard risk filters ───────────────────────────────────────────────────
    mcr = signals.get("mc_risk", mc_risk or {}) or {}
    if not isinstance(mcr, dict):
        mcr = {}
    var95 = float(mcr.get("var_95") or 0)
    regime = (signals.get("regime") or {}).get("regime", "Neutral")
    classic = signals.get("classic") or {}
    adx = signals.get("adx") or {}
    trend = signals.get("trend") or {}

    if action == "long":
        if var95 > 30 or regime == "Bear":
            action = "flat"
            risk = 0.0
            rationale = f"{rationale} | risk filter: VaR={var95}% regime={regime} → flat"
        elif var95 > 20:
            risk = max(0.002, risk * 0.5)
            rationale = f"{rationale} | size cut: elevated VaR {var95}%"
        macd_cross = str(classic.get("macd_cross", ""))
        stack = str(trend.get("stack", ""))
        adx_val = float(adx.get("adx") or 0)
        if overall < 65 and (
            macd_cross in ("Bearish", "BearishCross")
            or stack == "Bearish"
            or (adx_val >= 25 and float(adx.get("minus_di") or 0) > float(adx.get("plus_di") or 0))
        ):
            risk = max(0.002, risk * 0.5)
            rationale = f"{rationale} | trend caution: MACD/ADX/SMA stack"

    # High model disagreement → smaller size
    if action == "long" and isinstance(multi, dict):
        h5 = (multi.get("horizons") or {}).get("5d") or {}
        disagree = h5.get("model_disagreement")
        try:
            if disagree is not None and float(disagree) > 5:
                risk = max(0.002, risk * 0.7)
                rationale = f"{rationale} | size cut: model disagreement {disagree}"
        except (TypeError, ValueError):
            pass

    # ── Decision memory (Abzu-style episodic; code-enforced, not prose) ─────
    mem = memory if isinstance(memory, dict) else {}
    if mem:
        if action == "long" and mem.get("block_new_long"):
            action = "flat"
            risk = 0.0
            flags = ",".join(mem.get("flags") or []) or "cooldown"
            rationale = f"{rationale} | memory block: {flags}"
        elif action == "long":
            mult = float(mem.get("risk_multiplier") or 1.0)
            if mult < 1.0 and risk > 0:
                risk = max(0.002, risk * mult)
                flags = ",".join(mem.get("flags") or []) or f"mult={mult}"
                rationale = f"{rationale} | memory size cut: {flags}"

    # Stop hint (ATR-based when available)
    stop = None
    if isinstance(mcr, dict) and mcr.get("stop_price"):
        stop = mcr.get("stop_price")
    elif atr_pct > 0 and current_price > 0:
        stop = current_price * (1 - max(0.05, atr_pct / 100 * 1.5))
    elif current_price > 0:
        stop = current_price * 0.92  # default ~8% stop

    horizon = None
    if isinstance(multi, dict) and "horizons" in multi:
        for h in ["5d", "10d", "15d", "20d", "50d"]:
            hd = multi["horizons"].get(h, {})
            if isinstance(hd, dict) and "bull" in str(hd.get("direction", "")).lower():
                horizon = int(str(h).replace("d", ""))
                break

    return TradeSignal(
        ticker=scores.get("ticker", "UNKNOWN"),
        asof=str(scores.get("asof", scores.get("timestamp", "N/A")))[:10],
        action=action,
        conviction=q_conv,
        overall_score=overall,
        suggested_risk_pct=risk,
        stop_price=stop,
        target_price=None,
        horizon_days=horizon,
        rationale=rationale,
        raw_score=q_raw,
    )


def position_size_shares(
    equity: float,
    risk_pct: float,
    price: float,
    stop_price: Optional[float] = None,
    min_shares: int = 0,
    max_notional_pct: float = 0.95,
) -> int:
    """Risk-based size: shares ≈ (equity * risk_pct) / stop_distance, capped by cash.

    Never returns a size whose notional exceeds max_notional_pct * equity.
    """
    if equity <= 0 or risk_pct <= 0 or price <= 0:
        return 0
    if stop_price is not None and stop_price > 0 and stop_price < price:
        stop_dist = price - float(stop_price)
    else:
        stop_dist = price * 0.02
    stop_dist = max(stop_dist, price * 0.005)
    shares = int((equity * risk_pct) / stop_dist)
    max_shares = int((equity * max_notional_pct) / price)
    shares = min(shares, max_shares)
    if shares < 1:
        return 0
    if min_shares > 0:
        return max(min_shares, shares)
    return shares
