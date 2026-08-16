"""
Decision policy for the backtesting agent.

First principles (long-only swing agent):
1. Capital protection: refuse longs in structural breakdown (Bear regime,
   death-cross / Bearish stack with elevated tail risk).
2. Risk is continuous: moderate–high VaR sizes down; only *extreme* VaR
   hard-flats without requiring breakdown.
3. Separate "no trade" from "trade small" — do not equate VaR 31% in a Bull
   regime with VaR 61% + Bear (LLY vs TSLA lesson).
4. Entry needs a constructive path (score/conviction/trend/news); multi-horizon
   Path C remains opt-in research.
5. Memory cooldowns always win over new risk.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal, Tuple, List


Action = Literal["long", "short", "flat"]

# VaR ladder (MC 95% simulated annual-ish units from pipeline)
VAR_ELEVATED = 20.0   # size cut
VAR_HIGH = 30.0       # deep size cut unless structural breakdown → hard flat
VAR_EXTREME = 45.0    # hard flat regardless of trend/regime



@dataclass
class TradeSignal:
    """Clean, structured output from the agent at a point in time."""
    ticker: str
    asof: str
    action: Action
    conviction: str
    overall_score: float
    suggested_risk_pct: float
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    horizon_days: Optional[int] = None
    rationale: str = ""
    raw_score: Optional[int] = None
    risk_veto: Optional[Dict[str, Any]] = None


def _dir_bull(s: Any) -> bool:
    return "bull" in str(s or "").lower()


def _dir_bear(s: Any) -> bool:
    return "bear" in str(s or "").lower()


def _build_veto_object(
    decision: str,
    reason: str,
    reasons: List[str],
    missing: List[str],
    risk_pct: float,
    action: str,
    ticker: str,
    asof: str,
) -> Dict[str, Any]:
    """
    Build machine-readable veto object for Trader consumption.
    
    Stable schema:
      {
        "decision": "ALLOW" | "CUT" | "VETO",
        "reason": "<one-line, data-grounded>",
        "reasons": ["..."],
        "missing": ["var_95", ...],
        "risk_pct": <float or 0>,
        "action": "long" | "flat",
        "ticker": "...",
        "asof": "YYYY-MM-DD"
      }
    
    Trader branches on `decision` only:
      ALLOW = size as given
      CUT = use risk_pct (already reduced)
      VETO = do not enter / flatten, risk_pct=0
    """
    return {
        "decision": decision,
        "reason": reason,
        "reasons": reasons,
        "missing": missing,
        "risk_pct": risk_pct,
        "action": action,
        "ticker": ticker,
        "asof": asof,
    }


def extract_leverage_flags(signals: Dict[str, Any], quant_output: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Pure helper: normalize constructive/destructive channels from scores.signals
    (and optional quant). Used by default_policy and unit tests.
    
    Fail-closed: missing/non-finite VaR or regime → flags set to fail safe.
    """
    signals = signals or {}
    multi = signals.get("multi_horizon_forecasts") or signals.get("multi_h") or {}
    if not isinstance(multi, dict):
        multi = {}
    consensus = multi.get("consensus_direction", "Neutral")
    # Quant may carry multi_horizon too
    if quant_output and isinstance(quant_output, dict):
        qs = quant_output.get("quantitative_signals") or {}
        qmh = qs.get("multi_horizon") or {}
        if isinstance(qmh, dict) and qmh.get("consensus_direction"):
            # Prefer score multi_h if it has horizons; else quant
            if not multi.get("horizons") and qmh.get("consensus_direction"):
                consensus = qmh.get("consensus_direction", consensus)

    trend = signals.get("trend") or {}
    adx = signals.get("adx") or {}
    classic = signals.get("classic") or {}
    finbert = signals.get("finbert") or signals.get("finbert_sentiment") or {}
    regime_dict = signals.get("regime") or {}
    regime = regime_dict.get("regime") if isinstance(regime_dict, dict) else None
    mcr = signals.get("mc_risk") or {}

    stack = str(trend.get("stack") or "Unknown")
    golden = bool(trend.get("golden_cross"))
    death = bool(trend.get("death_cross"))
    adx_val = float(adx.get("adx") or 0)
    plus_di = float(adx.get("plus_di") or 0)
    minus_di = float(adx.get("minus_di") or 0)
    macd_cross = str(classic.get("macd_cross") or "Neutral")

    trend_bull = (
        stack == "Bullish"
        or golden
        or (adx_val >= 20 and plus_di > minus_di and stack != "Bearish")
        or macd_cross in ("Bullish", "BullishCross")
    ) and stack != "Bearish" and not death and macd_cross not in ("Bearish", "BearishCross")

    # Softer bull: stack bullish alone is enough even if MACD mixed
    trend_bull_soft = stack == "Bullish" or golden
    trend_bear = (
        stack == "Bearish"
        or death
        or (adx_val >= 20 and minus_di > plus_di)
        or macd_cross in ("Bearish", "BearishCross")
    )

    fb_score = float(finbert.get("sentiment_score") or 50.0)
    fb_label = str(finbert.get("overall_sentiment") or "Neutral")
    news_bull = fb_score >= 58.0 or _dir_bull(fb_label)
    news_bear = fb_score <= 42.0 or _dir_bear(fb_label)
    # Neutral stub when FinBERT disabled (exactly 50) — not a signal
    news_active = abs(fb_score - 50.0) > 0.5 or (
        fb_label not in ("Neutral", "Disabled", "N/A", "") and "disable" not in fb_label.lower()
    )

    # Fail-closed: missing/non-finite VaR → None (not 0)
    var95_raw = mcr.get("var_95")
    var95 = None
    if var95_raw is not None:
        try:
            var95_val = float(var95_raw)
            if not (var95_val != var95_val or var95_val == float('inf') or var95_val == float('-inf')):
                # finite
                var95 = var95_val
        except (TypeError, ValueError):
            pass
    
    # Structural breakdown: not just "MACD soft" — death cross / Bearish stack
    structural_breakdown = (
        stack == "Bearish"
        or death
        or (stack != "Bullish" and not golden and adx_val >= 25 and minus_di > plus_di + 5)
    )

    # Fail-closed: missing regime → treat as missing (None), not "Neutral"
    regime_str = str(regime).strip() if regime else None
    regime_missing = not regime_str or regime_str in ("", "None", "Unknown")
    
    return {
        "consensus": consensus,
        "consensus_bull": _dir_bull(consensus),
        "consensus_bear": _dir_bear(consensus),
        "trend_bull": trend_bull or trend_bull_soft,
        "trend_bull_strong": trend_bull and trend_bull_soft,
        "trend_bear": trend_bear,
        "structural_breakdown": structural_breakdown,
        "death_cross": death,
        "golden_cross": golden,
        "stack": stack,
        "macd_cross": macd_cross,
        "adx": adx_val,
        "news_bull": news_bull and news_active,
        "news_bear": news_bear and news_active,
        "news_active": news_active,
        "finbert_score": fb_score,
        "regime": regime_str,
        "regime_bear": regime_str == "Bear" if regime_str else False,
        "regime_bull": regime_str == "Bull" if regime_str else False,
        "regime_missing": regime_missing,
        "var95": var95,
        "var95_missing": var95 is None,
        "high_var": var95 > VAR_HIGH if var95 is not None else False,
        "elevated_var": var95 > VAR_ELEVATED if var95 is not None else False,
        "extreme_var": var95 > VAR_EXTREME if var95 is not None else False,
    }


def apply_risk_filters(
    action: Action,
    risk: float,
    rationale: str,
    lev: Dict[str, Any],
    overall: float,
    *,
    session: bool = False,
) -> Tuple[Action, float, str, List[str], List[str]]:
    """
    Layer risk on a proposed entry.

    Fail-closed hard flat (no new long):
      - Missing VaR or regime (cannot assess risk)
      - Bear regime
      - Extreme VaR (>45)
      - High VaR (>30) *and* structural breakdown (death/Bearish stack/…)
      - Bearish multi-h consensus on non-elite scores
      - Session: weak mid-score without strong trend

    Size cuts (still long when constructive):
      - High VaR without breakdown → deep cut
      - Elevated VaR → moderate cut
      - Soft trend/news caution → mild cut
    
    Returns: (action, risk, rationale, veto_reasons, missing_fields)
    """
    veto_reasons: List[str] = []
    missing_fields: List[str] = []
    
    if action != "long":
        return action, risk, rationale, veto_reasons, missing_fields

    # 0) Fail-closed: missing required risk data → flat
    if lev.get("var95_missing"):
        missing_fields.append("var_95")
        veto_reasons.append("VaR missing (fail closed)")
        return (
            "flat",
            0.0,
            f"{rationale} | risk filter: VaR missing (fail closed) → flat",
            veto_reasons,
            missing_fields,
        )
    if lev.get("regime_missing"):
        missing_fields.append("regime")
        veto_reasons.append("regime missing (fail closed)")
        return (
            "flat",
            0.0,
            f"{rationale} | risk filter: regime missing (fail closed) → flat",
            veto_reasons,
            missing_fields,
        )

    var95 = lev["var95"]
    regime = lev["regime"]

    # 1) Structural / regime hard blocks
    if lev["regime_bear"]:
        veto_reasons.append(f"Bear regime")
        return (
            "flat",
            0.0,
            f"{rationale} | risk filter: Bear regime → flat",
            veto_reasons,
            missing_fields,
        )
    if lev["extreme_var"]:
        veto_reasons.append(f"extreme VaR={var95}% (>{VAR_EXTREME})")
        return (
            "flat",
            0.0,
            f"{rationale} | risk filter: extreme VaR={var95}% (>{VAR_EXTREME}) → flat",
            veto_reasons,
            missing_fields,
        )
    if lev["high_var"] and lev["structural_breakdown"]:
        veto_reasons.append(f"VaR={var95}% + structural breakdown")
        return (
            "flat",
            0.0,
            f"{rationale} | risk filter: VaR={var95}% + structural breakdown "
            f"(stack={lev['stack']}, death_cross={lev.get('death_cross')}) → flat",
            veto_reasons,
            missing_fields,
        )

    # 2) Forecast consensus block (only when multi-h is meaningful)
    if lev["consensus_bear"] and overall < 68:
        veto_reasons.append("Bearish multi-horizon consensus")
        return (
            "flat",
            0.0,
            f"{rationale} | risk filter: Bearish multi-horizon consensus → flat",
            veto_reasons,
            missing_fields,
        )

    # 3) Graduated VaR sizing — high VaR longs need clear trend structure
    #    (Bullish stack or golden cross). Mixed + high VaR stays flat (TSLA May
    #    stabs) while LLY-style Bullish stack still trades small.
    if lev["high_var"]:
        clear_uptrend = (
            lev.get("stack") == "Bullish"
            or lev.get("golden_cross")
            or lev.get("trend_bull_strong")
        )
        if not clear_uptrend:
            veto_reasons.append(f"high VaR={var95}% without clear uptrend")
            return (
                "flat",
                0.0,
                f"{rationale} | risk filter: high VaR={var95}% without clear "
                f"uptrend (stack={lev.get('stack')}) → flat",
                veto_reasons,
                missing_fields,
            )
        risk = max(0.002, risk * 0.30)
        rationale = (
            f"{rationale} | size cut: high VaR {var95}% "
            f"(clear uptrend — not flat)"
        )
        veto_reasons.append(f"size cut: high VaR {var95}% (×0.30)")
    elif lev["elevated_var"]:
        risk = max(0.002, risk * 0.50)
        rationale = f"{rationale} | size cut: elevated VaR {var95}%"
        veto_reasons.append(f"size cut: elevated VaR {var95}% (×0.50)")

    if lev["trend_bear"] and overall < 65 and not lev["structural_breakdown"]:
        # Soft technical friction (e.g. MACD bearish under bullish stack)
        risk = max(0.002, risk * 0.50)
        rationale = f"{rationale} | trend caution: MACD/ADX/SMA stack"
        veto_reasons.append("trend caution (×0.50)")
    if lev["news_bear"]:
        risk = max(0.002, risk * 0.70)
        rationale = f"{rationale} | size cut: bearish FinBERT"
        veto_reasons.append("bearish FinBERT (×0.70)")

    if session and overall < 55 and not lev["trend_bull_strong"]:
        veto_reasons.append(f"session: score<{55} without strong trend")
        return (
            "flat",
            0.0,
            f"{rationale} | session filter: score<{55} without strong trend → flat",
            veto_reasons,
            missing_fields,
        )

    return action, risk, rationale, veto_reasons, missing_fields


def choose_entry(
    overall: float,
    q_conv: str,
    lev: Dict[str, Any],
    *,
    allow_multi_horizon_entry: bool = False,
) -> Tuple[Action, float, str]:
    """
    Multi-path entry. Returns (action, risk_pct, rationale) before hard risk filters.

    Path C (multi-horizon consensus leverage) is **off by default** — forecasts are
    research-only after the GME audit; opt in with allow_multi_horizon_entry=True.
    """
    conv = str(q_conv or "Medium")
    # Path A: classic high-quality (score + conviction; consensus only if multi-h entry enabled)
    if overall >= 70 and conv in ("High", "Medium"):
        if allow_multi_horizon_entry and lev["consensus_bull"]:
            risk = 0.015 if conv == "High" else 0.01
            return "long", risk, f"Score {overall} + Bullish consensus + {conv} conviction"
        if not allow_multi_horizon_entry or not lev["consensus_bear"]:
            # Without multi-h leverage: high score + Medium/High is enough if not bearish consensus
            if not lev["consensus_bear"]:
                risk = 0.012 if conv == "High" else 0.008
                return "long", risk, f"Score {overall} + {conv} conviction (research multi-h not required)"
    if overall >= 60 and conv == "High" and not lev["consensus_bear"]:
        return "long", 0.01, f"Score {overall} + High conviction (no bearish consensus)"

    # Path B: trend leverage (SMA/ADX/MACD) — participates in strong up trends
    if (
        overall >= 52
        and lev["trend_bull"]
        and not lev["consensus_bear"]
        and conv in ("High", "Medium")
        and not lev["regime_bear"]
    ):
        risk = 0.01 if conv == "High" or lev["trend_bull_strong"] else 0.007
        return (
            "long",
            risk,
            f"Score {overall} + bullish trend (stack={lev['stack']}) + {conv} conv",
        )

    # Path C: multi-horizon consensus leverage — opt-in only (default demoted)
    if (
        allow_multi_horizon_entry
        and overall >= 54
        and lev["consensus_bull"]
        and conv in ("High", "Medium")
        and not lev["trend_bear"]
        and not lev["regime_bear"]
    ):
        return (
            "long",
            0.008,
            f"Score {overall} + Bullish multi-horizon + {conv} conv",
        )

    # Path D: FinBERT/news constructive (only when news path is active)
    if (
        overall >= 53
        and lev["news_bull"]
        and not lev["consensus_bear"]
        and not lev["trend_bear"]
        and conv in ("High", "Medium")
        and not lev["regime_bear"]
    ):
        return (
            "long",
            0.007,
            f"Score {overall} + bullish FinBERT ({lev['finbert_score']}) + {conv} conv",
        )

    # Path E: strong trend alone with non-Low conviction and mid score
    if (
        overall >= 50
        and lev["trend_bull_strong"]
        and conv != "Low"
        and not lev["consensus_bear"]
        and not lev["regime_bear"]
        and not lev["news_bear"]
    ):
        return (
            "long",
            0.006,
            f"Score {overall} + strong bullish SMA stack + {conv} conv",
        )

    return (
        "flat",
        0.0,
        f"Score {overall}, {lev['consensus']}, {conv}, trend={lev['stack']} → flat",
    )


def default_policy(
    scores: Dict[str, Any],
    quant_output: Optional[Dict[str, Any]] = None,
    current_price: float = 0.0,
    atr_pct: float = 0.0,
    mc_risk: Optional[Dict[str, Any]] = None,
    profile: str = "Balanced",
    relaxed: bool = False,
    memory: Optional[Dict[str, Any]] = None,
    execution_mode: str = "swing",
    session_stop_pct: float = 0.015,
    allow_multi_horizon_entry: bool = False,
) -> TradeSignal:
    """
    Multi-signal decision policy: score + conviction + trend (+ optional multi-h) + news,
    then hard VaR/Bear filters and memory cooldowns.

    execution_mode:
      - swing: multi-day holds, wider ATR/MC stops
      - session: same-day open→close; tighter stops + slight risk haircut

    allow_multi_horizon_entry: Path C multi-horizon leverage (default False — research-only).
    """
    del relaxed
    session = str(execution_mode or "swing").lower() == "session"
    overall = float(scores.get("overall", 50.0))
    signals = scores.get("signals", {}) or {}
    if mc_risk and isinstance(mc_risk, dict):
        # Prefer explicit mc_risk arg if signals lack it
        if not signals.get("mc_risk"):
            signals = {**signals, "mc_risk": mc_risk}

    lev = extract_leverage_flags(signals, quant_output)

    q_conv = "Medium"
    q_raw = None
    if quant_output and isinstance(quant_output, dict):
        q_conv = quant_output.get("quantitative_conviction", "Medium") or "Medium"
        qs = quant_output.get("quantitative_signals", {}) or {}
        q_raw = qs.get("raw_conviction_score") if isinstance(qs, dict) else None
    if overall >= 75:
        q_conv = "High"
    elif overall < 42:
        # Slightly less aggressive Low clamp so mid-40s can still use trend paths with Medium quant
        q_conv = "Low"

    action, risk, rationale = choose_entry(
        overall, q_conv, lev, allow_multi_horizon_entry=allow_multi_horizon_entry
    )

    action, risk, rationale, veto_reasons, missing_fields = apply_risk_filters(
        action, risk, rationale, lev, overall, session=session
    )

    multi = signals.get("multi_horizon_forecasts") or signals.get("multi_h") or {}
    if action == "long" and isinstance(multi, dict):
        h5 = (multi.get("horizons") or {}).get("5d") or {}
        disagree = h5.get("model_disagreement")
        try:
            if disagree is not None and float(disagree) > 5:
                risk = max(0.002, risk * 0.7)
                rationale = f"{rationale} | size cut: model disagreement {disagree}"
        except (TypeError, ValueError):
            pass

    mem = memory if isinstance(memory, dict) else {}
    if mem:
        if action == "long" and mem.get("block_new_long"):
            action = "flat"
            risk = 0.0
            flags = ",".join(mem.get("flags") or []) or "cooldown"
            rationale = f"{rationale} | memory block: {flags}"
            veto_reasons.append(f"memory block: {flags}")
        elif action == "long":
            mult = float(mem.get("risk_multiplier") or 1.0)
            if mult < 1.0 and risk > 0:
                risk = max(0.002, risk * mult)
                flags = ",".join(mem.get("flags") or []) or f"mult={mult}"
                rationale = f"{rationale} | memory size cut: {flags}"
                veto_reasons.append(f"memory size cut: {flags}")

    mcr = signals.get("mc_risk", mc_risk or {}) or {}
    if not isinstance(mcr, dict):
        mcr = {}
    stop = None
    if session and current_price > 0:
        # Tight open→close stop: floor at session_stop_pct, widen with ATR up to 3%
        atr_stop_pct = max(
            session_stop_pct,
            min(0.03, (atr_pct / 100.0) if atr_pct > 0 else session_stop_pct),
        )
        stop = current_price * (1.0 - atr_stop_pct)
        if action == "long":
            rationale = f"{rationale} | session stop {atr_stop_pct * 100:.1f}%"
    elif mcr.get("stop_price"):
        stop = mcr.get("stop_price")
    elif atr_pct > 0 and current_price > 0:
        stop = current_price * (1 - max(0.05, atr_pct / 100 * 1.5))
    elif current_price > 0:
        stop = current_price * 0.92

    horizon = 1 if session else None
    if not session and isinstance(multi, dict) and "horizons" in multi:
        for h in ["5d", "10d", "15d", "20d", "50d"]:
            hd = multi["horizons"].get(h, {})
            if isinstance(hd, dict) and _dir_bull(hd.get("direction")):
                horizon = int(str(h).replace("d", ""))
                break

    # Build machine-readable veto object for Trader
    ticker = scores.get("ticker", "UNKNOWN")
    asof = str(scores.get("asof", scores.get("timestamp", "N/A")))[:10]
    
    # Determine decision: VETO if flat due to risk, CUT if size reduced, ALLOW otherwise
    decision = "ALLOW"
    if action == "flat" and veto_reasons:
        decision = "VETO"
    elif veto_reasons and risk < (0.002 if action == "long" else 0):
        # If we have reasons and risk was cut (heuristic: below entry minimums)
        decision = "CUT"
    elif action == "long" and risk > 0:
        decision = "ALLOW"
    
    primary_reason = veto_reasons[0] if veto_reasons else "No risk issues"
    
    risk_veto_obj = _build_veto_object(
        decision=decision,
        reason=primary_reason,
        reasons=veto_reasons,
        missing=missing_fields,
        risk_pct=risk,
        action=action,
        ticker=ticker,
        asof=asof,
    )
    
    return TradeSignal(
        ticker=ticker,
        asof=asof,
        action=action,
        conviction=q_conv,
        overall_score=overall,
        suggested_risk_pct=risk,
        stop_price=stop,
        target_price=None,
        horizon_days=horizon,
        rationale=rationale,
        raw_score=q_raw,
        risk_veto=risk_veto_obj,
    )


def position_size_shares(
    equity: float,
    risk_pct: float,
    price: float,
    stop_price: Optional[float] = None,
    min_shares: int = 0,
    max_notional_pct: float = 0.95,
) -> int:
    """Risk-based size capped by cash notional."""
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
