"""
Decision policy for the backtesting agent.

Uses multi-channel leverage (score, conviction, multi-horizon consensus,
SMA/ADX trend, FinBERT/news, memory) with hard risk filters (VaR, Bear regime).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal, Tuple, List


Action = Literal["long", "short", "flat"]


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


def _dir_bull(s: Any) -> bool:
    return "bull" in str(s or "").lower()


def _dir_bear(s: Any) -> bool:
    return "bear" in str(s or "").lower()


def extract_leverage_flags(signals: Dict[str, Any], quant_output: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Pure helper: normalize constructive/destructive channels from scores.signals
    (and optional quant). Used by default_policy and unit tests.
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
    regime = (signals.get("regime") or {}).get("regime", "Neutral")
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

    var95 = float(mcr.get("var_95") or 0)

    return {
        "consensus": consensus,
        "consensus_bull": _dir_bull(consensus),
        "consensus_bear": _dir_bear(consensus),
        "trend_bull": trend_bull or trend_bull_soft,
        "trend_bull_strong": trend_bull and trend_bull_soft,
        "trend_bear": trend_bear,
        "stack": stack,
        "macd_cross": macd_cross,
        "adx": adx_val,
        "news_bull": news_bull and news_active,
        "news_bear": news_bear and news_active,
        "news_active": news_active,
        "finbert_score": fb_score,
        "regime": regime,
        "regime_bear": str(regime) == "Bear",
        "var95": var95,
        "high_var": var95 > 30,
        "elevated_var": var95 > 20,
    }


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

    # ── Hard risk filters ───────────────────────────────────────────────────
    var95 = lev["var95"]
    regime = lev["regime"]

    if action == "long":
        if lev["high_var"] or lev["regime_bear"]:
            action = "flat"
            risk = 0.0
            rationale = f"{rationale} | risk filter: VaR={var95}% regime={regime} → flat"
        elif lev["consensus_bear"] and overall < 68:
            # Soft paths cannot fight bearish ensemble; classic high score still blocked unless very strong
            action = "flat"
            risk = 0.0
            rationale = f"{rationale} | risk filter: Bearish multi-horizon consensus → flat"
        elif lev["elevated_var"]:
            risk = max(0.002, risk * 0.5)
            rationale = f"{rationale} | size cut: elevated VaR {var95}%"
        if action == "long" and lev["trend_bear"] and overall < 65:
            risk = max(0.002, risk * 0.5)
            rationale = f"{rationale} | trend caution: MACD/ADX/SMA stack"
        if action == "long" and lev["news_bear"]:
            risk = max(0.002, risk * 0.7)
            rationale = f"{rationale} | size cut: bearish FinBERT"
        # Session: avoid weak mid-score longs (round-trip cost sensitivity)
        if session and action == "long" and overall < 55 and not lev["trend_bull_strong"]:
            action = "flat"
            risk = 0.0
            rationale = f"{rationale} | session filter: score<{55} without strong trend → flat"

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
        elif action == "long":
            mult = float(mem.get("risk_multiplier") or 1.0)
            if mult < 1.0 and risk > 0:
                risk = max(0.002, risk * mult)
                flags = ",".join(mem.get("flags") or []) or f"mult={mult}"
                rationale = f"{rationale} | memory size cut: {flags}"

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
