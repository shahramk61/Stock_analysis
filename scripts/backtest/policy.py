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

    # Policy: score + consensus + conviction (informed by report thresholds + quant)
    if overall >= 70 and str(consensus).lower() == "bullish" and q_conv in ("High", "Medium"):
        action: Action = "long"
        risk = 0.015 if q_conv == "High" else 0.01
        rationale = f"Score {overall} + Bullish + {q_conv} conviction"
    elif overall >= 60 and q_conv == "High":
        action = "long"
        risk = 0.01
        rationale = f"Score {overall} + High conviction"
    else:
        action = "flat"
        risk = 0.0
        rationale = f"Score {overall}, {consensus}, {q_conv} → flat"

    # Stop hint
    stop = None
    mcr = signals.get("mc_risk", mc_risk or {})
    if isinstance(mcr, dict) and mcr.get("stop_price"):
        stop = mcr.get("stop_price")
    elif atr_pct > 0:
        stop = current_price * (1 - max(0.05, atr_pct / 100 * 1.5))

    horizon = None
    if isinstance(multi, dict) and "horizons" in multi:
        for h in ["5d", "10d", "15d", "20d"]:
            hd = multi["horizons"].get(h, {})
            if isinstance(hd, dict) and hd.get("direction") == "Bullish":
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


# TODO (bt-06): Make thresholds/profile-dependent. Add short rules. Add hard risk filters (high VaR → flat).
# TODO: richer rationale including pillar contributions or top negative factors from quant warnings.
# TODO: support passing full quant node output directly.
