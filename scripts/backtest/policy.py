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
    relaxed: bool = False,   # Relaxed thresholds for demos / to exercise the trading simulator (entries, exits, P&L). Not for production use.
) -> TradeSignal:
    """
    MVP policy. Uses:
    - scores['overall'] (and pillars if needed)
    - quant_output['quantitative_conviction'] + raw etc. (preferred)
    - multi-horizon consensus/direction from scores['signals'] or quant
    - MC/ATR for risk sizing/stop hints

    This is deliberately simple and tunable. Matches spirit of current report recs + quant agent.
    """
    overall = scores.get("overall", 50.0)
    signals = scores.get("signals", {})
    multi = signals.get("multi_horizon_forecasts") or signals.get("multi_h", {}) or {}
    consensus = multi.get("consensus_direction", "Neutral") if isinstance(multi, dict) else "Neutral"

    # Conviction from quant (preferred) or derive from score
    q_conv = "Medium"
    q_raw = None
    if quant_output and isinstance(quant_output, dict):
        q_conv = quant_output.get("quantitative_conviction", "Medium")
        qs = quant_output.get("quantitative_signals", {}) or {}
        q_raw = qs.get("raw_conviction_score") if isinstance(qs, dict) else None
    if overall >= 75:
        q_conv = "High"
    elif overall < 45:
        q_conv = "Low"
    # Note: the quant debate contribution can produce "High" even at overall=50 when positives (quality, earnings) outweigh risks in its internal scoring; we now let that drive trades at 50.

    # Policy: score + consensus + conviction (informed by report thresholds + quant)
    if overall >= 70 and str(consensus).lower() == "bullish" and q_conv in ("High", "Medium"):
        action: Action = "long"
        risk = 0.015 if q_conv == "High" else 0.01
        rationale = f"Score {overall} + Bullish + {q_conv} conviction"
    elif overall >= 50 and q_conv == "High":
        action = "long"
        risk = 0.01
        rationale = f"Score {overall} + High conviction (from quant debate expert)"
    elif overall >= 45 and q_conv == "High":
        # Additional path: High conviction from the rich quant debate can trigger small longs even at lower scores
        # (the debate itself is already flagging the risks like high VaR)
        action = "long"
        risk = 0.005
        rationale = f"Score {overall} + High conviction from quant (relaxed threshold for High expert view)"
    else:
        action = "flat"
        risk = 0.0
        rationale = f"Score {overall}, {consensus}, {q_conv} → flat"

    # Relaxed demo mode: lower the bar so we can observe actual trades, position sizing,
    # costs, P&L, equity curve updates, etc. in the simulator.
    # When forecasts are disabled (--no-forecasts), it still allows longs at ~50 for pure demo purposes
    # so the trading engine (sizing using your --risk, simulator loop, etc.) can be exercised.
    # The base policy and non-forecast risk signals (high VaR, regime, etc.) are the reason for flat in strict mode.
    if relaxed and action == "flat":
        near_term_bullish = False
        if isinstance(multi, dict) and "horizons" in multi:
            h5 = multi["horizons"].get("5d", {}) or {}
            if isinstance(h5, dict) and str(h5.get("direction", "")).lower() == "bullish":
                near_term_bullish = True
        # Also check quant multi-horizon if present
        if not near_term_bullish and quant_output:
            qmh = (quant_output.get("quantitative_signals") or {}).get("multi_horizon", {})
            if isinstance(qmh, dict):
                qh = (qmh.get("horizons") or {}).get("5d", {}) or {}
                if isinstance(qh, dict) and str(qh.get("direction", "")).lower() == "bullish":
                    near_term_bullish = True

        if overall >= 48 and (str(consensus).lower() == "bullish" or near_term_bullish):
            action = "long"
            risk = 0.008   # smaller risk in relaxed demo mode
            rationale = f"Score {overall}, {consensus} (relaxed demo: 5d bullish) → long"
        elif overall >= 45 and near_term_bullish and q_conv != "Low":
            action = "long"
            risk = 0.005
            rationale = f"Score {overall} + near-term Bullish (relaxed demo) → long"
        elif overall >= 50 and near_term_bullish:
            # Very permissive for demo purposes on mixed 50-ish scores that still have positive short-term forecasts
            action = "long"
            risk = 0.005
            rationale = f"Score {overall} + 5d Bullish (relaxed thresholds for simulator demo) → long"
        elif overall >= 50 and relaxed:
            # Pure demo fallback: allow long at neutral 50 when --relaxed (even without forecast signals).
            # This lets you exercise the full simulator (sizing with your --risk, entry/exit logic, P&L, equity curve, etc.).
            # We also check for mitigating positive non-forecast signals (earnings surprise or High quality) so it's not completely ignoring the risk data.
            pos_earnings = False
            pos_quality = False
            if quant_output:
                qsig = quant_output.get("quantitative_signals", {}) or {}
                if qsig.get("earnings_surprise") and isinstance(qsig.get("earnings_surprise"), (int, float)) and qsig.get("earnings_surprise") > 5:
                    pos_earnings = True
                if (qsig.get("quality") or {}).get("quality") == "High":
                    pos_quality = True
            if pos_earnings or pos_quality:
                rationale = f"Score {overall} (relaxed demo — positive earnings/quality signals present) → long"
            else:
                rationale = f"Score {overall} (relaxed demo fallback) → long"
            action = "long"
            risk = 0.005

    # ── Hard risk filters (strict mode) ─────────────────────────────────────
    mcr = signals.get("mc_risk", mc_risk or {}) or {}
    if not isinstance(mcr, dict):
        mcr = {}
    var95 = float(mcr.get("var_95") or 0)
    regime = (signals.get("regime") or {}).get("regime", "Neutral")
    classic = signals.get("classic") or {}
    adx = signals.get("adx") or {}
    trend = signals.get("trend") or {}

    if not relaxed and action == "long":
        if var95 > 30 or regime == "Bear":
            action = "flat"
            risk = 0.0
            rationale = f"{rationale} | risk filter: VaR={var95}% regime={regime} → flat"
        elif var95 > 20:
            risk = max(0.002, risk * 0.5)
            rationale = f"{rationale} | size cut: elevated VaR {var95}%"
        # Trend / MACD conflict: cut size when strong bearish structure
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
    min_shares: int = 1,
) -> int:
    """Risk-based position size: shares ≈ (equity * risk_pct) / stop_distance."""
    if equity <= 0 or risk_pct <= 0 or price <= 0:
        return 0
    if stop_price is not None and stop_price > 0 and stop_price < price:
        stop_dist = price - stop_price
    else:
        stop_dist = price * 0.02  # 2% default risk distance
    stop_dist = max(stop_dist, price * 0.005)
    shares = int((equity * risk_pct) / stop_dist)
    return max(min_shares, shares) if shares > 0 else 0
