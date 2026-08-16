"""
Risk veto gate: ALLOW / CUT / VETO for proposed trades.

Risk mandate: fail closed. Missing VaR, regime, or asof → VETO.
Research BUY labels cannot override a VETO.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple


# Decision outcomes
VET_ALLOW = "ALLOW"
VET_CUT = "CUT"
VET_VETO = "VETO"

VetOutcome = Literal["ALLOW", "CUT", "VETO"]

# VaR ladder from policy.py (reused here as Risk authority)
VAR_ELEVATED = 20.0   # size cut
VAR_HIGH = 30.0       # deep size cut unless constructive structure → hard flat
VAR_EXTREME = 45.0    # hard flat regardless of trend/regime


@dataclass
class VetoReason:
    """Single reason for CUT or VETO."""
    category: str
    detail: str
    severity: VetOutcome = VET_VETO


@dataclass
class RiskDecision:
    """Structured output from risk veto gate."""
    outcome: VetOutcome
    risk_pct: float
    reasons: List[VetoReason] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    def vetoed(self) -> bool:
        return self.outcome == VET_VETO

    def cut(self) -> bool:
        return self.outcome == VET_CUT

    def allowed(self) -> bool:
        return self.outcome == VET_ALLOW

    def to_veto_object(
        self,
        action: str = "flat",
        ticker: str = "",
        asof: str = "",
    ) -> Dict[str, Any]:
        """
        Export machine-readable veto object for Trader consumption.
        
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
        reason_details = [r.detail for r in self.reasons]
        primary_reason = reason_details[0] if reason_details else "No issues"
        
        # action: if VETO, force flat
        final_action = "flat" if self.vetoed() else str(action).strip().lower()
        
        return {
            "decision": self.outcome,
            "reason": primary_reason,
            "reasons": reason_details,
            "missing": self.missing,
            "risk_pct": self.risk_pct,
            "action": final_action,
            "ticker": ticker,
            "asof": asof,
        }


def _is_finite(val: Any) -> bool:
    """True if val is a finite number (not None, not NaN, not inf)."""
    if val is None:
        return False
    try:
        f = float(val)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False


def _check_required_fields(
    asof: Optional[str],
    var_95: Any,
    regime: Any,
) -> Tuple[List[str], List[VetoReason]]:
    """
    Verify required point-in-time fields for any new long.
    Returns (missing_fields, veto_reasons).
    """
    missing: List[str] = []
    reasons: List[VetoReason] = []

    if not asof or not isinstance(asof, str) or len(str(asof).strip()) < 10:
        missing.append("asof")
        reasons.append(VetoReason(
            category="missing_data",
            detail="asof date missing or invalid",
            severity=VET_VETO,
        ))

    if not _is_finite(var_95):
        missing.append("var_95")
        reasons.append(VetoReason(
            category="missing_data",
            detail="var_95 missing or non-finite (pipeline mc_risk required)",
            severity=VET_VETO,
        ))

    if not regime or not isinstance(regime, str) or str(regime).strip() == "":
        missing.append("regime")
        reasons.append(VetoReason(
            category="missing_data",
            detail="regime missing (signals.regime.regime required)",
            severity=VET_VETO,
        ))

    return missing, reasons


def _check_lookahead_flags(
    live_leak: bool,
    fundamentals_pit: bool,
) -> List[VetoReason]:
    """
    Veto if caller signals lookahead contamination.
    live_leak=True or fundamentals_pit=False in replay/asof mode → VETO.
    """
    reasons: List[VetoReason] = []

    if live_leak:
        reasons.append(VetoReason(
            category="lookahead",
            detail="live_leak=True: live data in point-in-time replay",
            severity=VET_VETO,
        ))

    if not fundamentals_pit:
        reasons.append(VetoReason(
            category="lookahead",
            detail="fundamentals_pit=False: non-PIT fundamentals in replay",
            severity=VET_VETO,
        ))

    return reasons


def _check_regime_veto(regime: str) -> Optional[VetoReason]:
    """Bear regime → VETO new longs (capital protection)."""
    if str(regime).strip() == "Bear":
        return VetoReason(
            category="regime",
            detail="Bear regime: capital protection blocks new longs",
            severity=VET_VETO,
        )
    return None


def _check_var_thresholds(
    var_95: float,
    structural_breakdown: bool,
    clear_uptrend: bool,
) -> Tuple[Optional[VetoReason], float]:
    """
    Apply VaR ladder. Returns (veto_reason_or_None, risk_multiplier).
    - Extreme VaR (>45) → VETO regardless of structure
    - High VaR (>30) + structural breakdown → VETO
    - High VaR (>30) without clear uptrend → VETO
    - High VaR (>30) with clear uptrend → deep cut (×0.30)
    - Elevated VaR (>20) → moderate cut (×0.50)
    """
    if var_95 > VAR_EXTREME:
        return (
            VetoReason(
                category="var_extreme",
                detail=f"VaR {var_95:.1f}% > {VAR_EXTREME}% (extreme risk)",
                severity=VET_VETO,
            ),
            0.0,
        )

    if var_95 > VAR_HIGH:
        if structural_breakdown:
            return (
                VetoReason(
                    category="var_high_breakdown",
                    detail=f"VaR {var_95:.1f}% + structural breakdown",
                    severity=VET_VETO,
                ),
                0.0,
            )
        if not clear_uptrend:
            return (
                VetoReason(
                    category="var_high_no_uptrend",
                    detail=f"VaR {var_95:.1f}% without clear uptrend",
                    severity=VET_VETO,
                ),
                0.0,
            )
        # High VaR with clear uptrend: trade small (deep cut)
        return None, 0.30

    if var_95 > VAR_ELEVATED:
        # Elevated VaR: moderate cut
        return None, 0.50

    # VaR acceptable: no cut
    return None, 1.0


def _check_cvar(cvar_95: Any, mc_metadata: Optional[Dict[str, Any]] = None) -> Optional[VetoReason]:
    """
    CVaR check: must be from actual Monte Carlo sim, not fallback.
    
    Hard rule from CoS/Quant:
    - cvar_95 is valid ONLY when MC sim actually ran
    - If cvar_95 in {20.0, 28.0} (old helper fallbacks) without MC evidence → treat as missing
    - Missing CVaR → VETO (fail closed)
    
    MC evidence: mc_metadata with paths/simulations count or non-fallback flag.
    """
    # If CVaR is missing or non-finite, fail closed
    if not _is_finite(cvar_95):
        return VetoReason(
            category="missing_cvar",
            detail="cvar_95 missing or non-finite (Quant pipeline must emit CVaR from MC sim)",
            severity=VET_VETO,
        )
    
    cvar_val = float(cvar_95)
    
    # Detect hardcoded fallback values (20.0, 28.0) without MC evidence
    is_fallback_value = abs(cvar_val - 20.0) < 0.01 or abs(cvar_val - 28.0) < 0.01
    
    if is_fallback_value:
        # Check for MC evidence
        mc_ran = False
        if mc_metadata and isinstance(mc_metadata, dict):
            # Evidence: paths > 0, simulations > 0, or explicit non-fallback flag
            paths = mc_metadata.get("paths") or mc_metadata.get("n_paths") or 0
            sims = mc_metadata.get("simulations") or mc_metadata.get("n_simulations") or 0
            is_fallback_flag = mc_metadata.get("is_fallback") or mc_metadata.get("fallback")
            
            # If we have paths/sims and no fallback flag, MC ran
            if (paths > 0 or sims > 0) and not is_fallback_flag:
                mc_ran = True
        
        if not mc_ran:
            # Hardcoded fallback without MC evidence → treat as missing
            return VetoReason(
                category="missing_cvar",
                detail=f"cvar_95={cvar_val} is hardcoded fallback (no MC sim evidence); treat as missing",
                severity=VET_VETO,
            )
    
    # CVaR present and either not a fallback value or has MC evidence
    return None


def _check_memory(memory_snapshot: Optional[Dict[str, Any]]) -> Tuple[Optional[VetoReason], float]:
    """
    Memory-based veto / cut.
    - Stop cooldown active → VETO new longs
    - Loss streak ≥2 → CUT (×0.5)
    Returns (veto_reason_or_None, risk_multiplier).
    """
    if not memory_snapshot or not isinstance(memory_snapshot, dict):
        return None, 1.0

    if memory_snapshot.get("block_new_long"):
        flags = memory_snapshot.get("flags") or []
        flag_str = ", ".join(flags) if flags else "cooldown"
        return (
            VetoReason(
                category="memory_cooldown",
                detail=f"Stop cooldown active: {flag_str}",
                severity=VET_VETO,
            ),
            0.0,
        )

    risk_mult = float(memory_snapshot.get("risk_multiplier") or 1.0)
    if risk_mult < 1.0:
        # Loss streak or other memory-based cut
        return None, risk_mult

    return None, 1.0


def _check_concentration(
    action: str,
    ticker: str,
    proposed_notional: float,
    book: Optional[Dict[str, float]],
    correlations: Optional[Dict[Tuple[str, str], float]],
    single_name_cap: float = 0.25,
    cluster_cap: float = 0.40,
    high_corr_threshold: float = 0.70,
) -> Optional[VetoReason]:
    """
    Concentration / correlation check when adding a name.
    - If action != 'long' → pass (no new exposure)
    - If proposed_notional <= 0 → pass (not sizing a position; concentration N/A)
    - If book is provided and ticker in book → pass (existing position, not adding)
    - If proposed_notional > 0 and book is None → VETO (cannot verify concentration)
    - Single-name notional cap (default 25%)
    - Correlated cluster cap (default 40% for names with corr > 0.70)
    """
    if action != "long":
        return None
    
    # If proposed_notional is 0, we're not sizing a position (concentration N/A)
    if proposed_notional <= 0:
        return None
    
    # If book is provided and ticker exists → not adding a new name
    if book is not None and ticker in book:
        return None
    
    # If we're sizing a position (proposed_notional > 0) and book is None,
    # we can't verify concentration → VETO
    if book is None:
        return VetoReason(
            category="missing_book",
            detail="Cannot verify concentration: book snapshot required when adding new name",
            severity=VET_VETO,
        )

    # Check single-name cap
    total_notional = sum(abs(v) for v in book.values()) + proposed_notional
    if total_notional > 0:
        single_weight = proposed_notional / total_notional
        if single_weight > single_name_cap:
            return VetoReason(
                category="concentration_single",
                detail=f"Single-name weight {single_weight:.1%} > {single_name_cap:.0%} cap",
                severity=VET_VETO,
            )

    # Check cluster cap (if correlations provided)
    if correlations is not None:
        # Find highly correlated existing names
        cluster_notional = proposed_notional
        cluster_tickers = [ticker]
        for existing_ticker, notional in book.items():
            corr_key = tuple(sorted([ticker, existing_ticker]))
            corr = correlations.get(corr_key)
            if corr is not None and corr > high_corr_threshold:
                cluster_notional += abs(notional)
                cluster_tickers.append(existing_ticker)

        if total_notional > 0:
            cluster_weight = cluster_notional / total_notional
            if cluster_weight > cluster_cap:
                return VetoReason(
                    category="concentration_cluster",
                    detail=(
                        f"Cluster {cluster_tickers} weight {cluster_weight:.1%} > "
                        f"{cluster_cap:.0%} cap (corr > {high_corr_threshold:.0%})"
                    ),
                    severity=VET_VETO,
                )

    return None


def vet_trade(
    action: str,
    ticker: str,
    asof: Optional[str],
    proposed_risk_pct: float,
    *,
    var_95: Any = None,
    cvar_95: Any = None,
    regime: Any = None,
    structural_breakdown: bool = False,
    clear_uptrend: bool = False,
    memory_snapshot: Optional[Dict[str, Any]] = None,
    book: Optional[Dict[str, float]] = None,
    correlations: Optional[Dict[Tuple[str, str], float]] = None,
    live_leak: bool = False,
    fundamentals_pit: bool = True,
    proposed_notional: float = 0.0,
    require_cvar: bool = False,
    mc_metadata: Optional[Dict[str, Any]] = None,
) -> RiskDecision:
    """
    Risk veto gate: ALLOW / CUT / VETO a proposed trade.

    Required for any new long:
      - asof (YYYY-MM-DD)
      - var_95 (from pipeline mc_risk, finite)
      - regime (from signals.regime.regime, non-empty string)

    Missing required fields → VETO.
    live_leak=True or fundamentals_pit=False in replay → VETO.
    Bear regime → VETO.
    Extreme VaR / high VaR without uptrend → VETO.
    Stop cooldown → VETO.
    Loss streak → CUT.

    Args:
        action: "long", "short", "flat"
        ticker: ticker symbol
        asof: point-in-time date (YYYY-MM-DD)
        proposed_risk_pct: base risk % from policy (before risk cuts)
        var_95: VaR 95% from mc_risk pipeline (required, fail closed if missing)
        cvar_95: CVaR 95% from MC sim (optional; if require_cvar=True → fail closed)
        regime: regime from signals.regime.regime (required, fail closed if missing)
        structural_breakdown: death cross / Bearish stack (affects high VaR veto)
        clear_uptrend: Bullish stack / golden cross (high VaR can trade small if True)
        memory_snapshot: output of DecisionMemory.apply_to_policy_inputs()
        book: current book {ticker: notional}, for concentration checks when adding
        correlations: pairwise correlations {(t1, t2): corr}, for cluster checks
        live_leak: True if live data leaked into replay (VETO)
        fundamentals_pit: False if non-PIT fundamentals used in replay (VETO)
        proposed_notional: proposed notional for this trade (for concentration)
        require_cvar: if True, missing CVaR → VETO (default False; opt-in)
        mc_metadata: Monte Carlo metadata (paths, simulations, fallback flags) to verify CVaR validity

    Returns:
        RiskDecision with outcome (ALLOW/CUT/VETO), final risk_pct, reasons, missing fields.
    """
    action = str(action or "flat").strip().lower()
    if action not in ("long", "short"):
        # Flat / unknown → no veto needed
        return RiskDecision(outcome=VET_ALLOW, risk_pct=0.0)

    if action == "short":
        # Short not implemented yet; defer to PM
        return RiskDecision(outcome=VET_ALLOW, risk_pct=proposed_risk_pct)

    # === LONG: apply all veto checks ===
    reasons: List[VetoReason] = []
    missing: List[str] = []
    risk_mult = 1.0

    # 1) Required fields
    miss_fields, miss_reasons = _check_required_fields(asof, var_95, regime)
    missing.extend(miss_fields)
    reasons.extend(miss_reasons)

    # 2) Lookahead flags
    lookahead_reasons = _check_lookahead_flags(live_leak, fundamentals_pit)
    reasons.extend(lookahead_reasons)

    # If any required field missing or lookahead → VETO immediately
    if missing or lookahead_reasons:
        return RiskDecision(
            outcome=VET_VETO,
            risk_pct=0.0,
            reasons=reasons,
            missing=missing,
        )

    # 3) Regime veto
    regime_str = str(regime).strip()
    regime_reason = _check_regime_veto(regime_str)
    if regime_reason:
        reasons.append(regime_reason)
        return RiskDecision(
            outcome=VET_VETO,
            risk_pct=0.0,
            reasons=reasons,
            missing=missing,
        )

    # 4) VaR thresholds
    var_val = float(var_95)
    var_reason, var_mult = _check_var_thresholds(var_val, structural_breakdown, clear_uptrend)
    if var_reason:
        reasons.append(var_reason)
        return RiskDecision(
            outcome=VET_VETO,
            risk_pct=0.0,
            reasons=reasons,
            missing=missing,
        )
    risk_mult *= var_mult
    if var_mult < 1.0:
        reasons.append(VetoReason(
            category="var_size_cut",
            detail=f"VaR {var_val:.1f}%: size ×{var_mult:.2f}",
            severity=VET_CUT,
        ))

    # 5) CVaR (opt-in fail-closed, detects hardcoded fallbacks)
    if require_cvar:
        cvar_reason = _check_cvar(cvar_95, mc_metadata=mc_metadata)
        if cvar_reason:
            reasons.append(cvar_reason)
            missing.append("cvar_95")
            return RiskDecision(
                outcome=VET_VETO,
                risk_pct=0.0,
                reasons=reasons,
                missing=missing,
            )

    # 6) Memory (cooldown → VETO; loss streak → CUT)
    mem_reason, mem_mult = _check_memory(memory_snapshot)
    if mem_reason:
        reasons.append(mem_reason)
        return RiskDecision(
            outcome=VET_VETO,
            risk_pct=0.0,
            reasons=reasons,
            missing=missing,
        )
    risk_mult *= mem_mult
    if mem_mult < 1.0:
        flags = (memory_snapshot or {}).get("flags") or []
        flag_str = ", ".join(flags) if flags else f"mult={mem_mult}"
        reasons.append(VetoReason(
            category="memory_size_cut",
            detail=f"Memory: {flag_str} → size ×{mem_mult:.2f}",
            severity=VET_CUT,
        ))

    # 7) Concentration / correlation
    conc_reason = _check_concentration(
        action, ticker, proposed_notional, book, correlations
    )
    if conc_reason:
        reasons.append(conc_reason)
        return RiskDecision(
            outcome=VET_VETO,
            risk_pct=0.0,
            reasons=reasons,
            missing=missing,
        )

    # All checks passed or only size cuts
    final_risk = max(0.0, proposed_risk_pct * risk_mult)
    outcome = VET_CUT if risk_mult < 1.0 else VET_ALLOW

    return RiskDecision(
        outcome=outcome,
        risk_pct=final_risk,
        reasons=reasons,
        missing=missing,
    )
