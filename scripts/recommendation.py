"""
Dual recommendation labels: research (score bands) vs execution (policy action).

Audit finding: text BUY / DCF upside must not be read as a trade ticket when
policy_hint is flat. Agents and JSON consumers should always see both layers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def research_recommendation(overall: float) -> str:
    """Score-band research label (not an order)."""
    o = float(overall or 0.0)
    if o >= 75:
        return "STRONG_BUY"
    if o >= 60:
        return "BUY"
    if o >= 50:
        return "HOLD"
    if o >= 35:
        return "CAUTION"
    return "SELL"


def execution_label(action: Optional[str]) -> str:
    a = str(action or "flat").strip().lower()
    if a in ("long", "buy"):
        return "LONG"
    if a in ("short",):
        return "SHORT"
    return "FLAT"


def research_vs_execution_conflict(
    research: str,
    execution_action: Optional[str],
) -> bool:
    """True when research is constructive but execution is not risk-on long."""
    r = str(research or "").upper()
    a = str(execution_action or "flat").strip().lower()
    research_bull = r in ("BUY", "STRONG_BUY")
    exec_not_long = a not in ("long", "buy")
    return research_bull and exec_not_long


def dual_recommendation(
    overall: float,
    *,
    policy_action: Optional[str] = None,
    policy_conviction: Optional[str] = None,
    policy_rationale: Optional[str] = None,
    suggested_risk_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Build dual labels for reports/handoffs.

    - research_recommendation: score bands only
    - execution_action / execution_label: from policy (flat/long/short)
    - recommendation: combined display string
    - policy_conflict: research BUY* vs execute non-long
    """
    research = research_recommendation(overall)
    action = str(policy_action or "flat").strip().lower()
    if action in ("buy", "hold", "sell"):
        # normalize report verbs if callers pass them
        action = {"buy": "long", "hold": "flat", "sell": "flat"}.get(action, action)
    exec_lab = execution_label(action)
    conflict = research_vs_execution_conflict(research, action)
    display = f"Research {research} | Execute {exec_lab}"
    note = (
        "Research labels score bands only. "
        "Execute is the policy/trade intent — do not size from Research BUY when Execute is FLAT."
    )
    if conflict:
        note += " policy_conflict: research constructive but execution blocked (risk filters)."

    return {
        "research_recommendation": research,
        "execution_action": action if policy_action is not None else None,
        "execution_label": exec_lab if policy_action is not None else None,
        "execution_conviction": policy_conviction,
        "suggested_risk_pct": suggested_risk_pct,
        "recommendation": display if policy_action is not None else research,
        "recommendation_note": note,
        "policy_conflict": conflict if policy_action is not None else None,
        "policy_rationale": policy_rationale,
    }


def format_research_line(overall: float) -> str:
    r = research_recommendation(overall)
    emoji = {
        "STRONG_BUY": "🟢 STRONG BUY",
        "BUY": "🟡 BUY",
        "HOLD": "⚪ HOLD",
        "CAUTION": "🟠 CAUTION",
        "SELL": "🔴 SELL",
    }.get(r, r)
    return emoji
