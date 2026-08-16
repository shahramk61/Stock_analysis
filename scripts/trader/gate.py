"""
Execute gate: combine risk_veto, policy_hint, dual_recommendation, decision memory, 
session clock, and tape quality.

Risk veto hierarchy (fail closed):
1. Missing/invalid risk_veto → flat (fail closed for NEW risk)
2. VETO → flat, risk = 0
3. CUT → keep long only if policy says long; use risk_veto.risk_pct (if null → flat)
4. ALLOW → still apply clock/tape/policy/memory gates

Research BUY must never become a long when Execute is FLAT.
Memory block_new_long wins. Closed market / missing tape → flat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .session_clock import MarketSession, should_allow_new_trades
from .levels import TradeLevels


@dataclass
class ExecuteGate:
    """
    Execute gating decision combining all timing/tape/memory/risk factors.
    
    would_be_flat: True if any gate blocks execution
    execute_action: final action after all gates applied
    final_risk_pct: final risk percentage after all gates (may be from risk_veto)
    reasons: list of reasons for the decision
    """
    would_be_flat: bool
    execute_action: str  # "long", "flat", "short"
    final_risk_pct: Optional[float]  # Final risk % (from risk_veto if CUT)
    reasons: List[str]
    
    # Component states
    policy_hint_action: Optional[str] = None
    dual_execute_label: Optional[str] = None
    research_label: Optional[str] = None
    risk_veto_decision: Optional[str] = None  # ALLOW | CUT | VETO
    risk_veto_blocks: bool = False
    memory_blocks: bool = False
    session_blocks: bool = False
    tape_blocks: bool = False
    policy_conflict: bool = False  # Research bullish but Execute flat


def normalize_action(action: Any) -> str:
    """Normalize action to long/flat/short."""
    s = str(action or "flat").strip().lower()
    if s in ("buy", "long"):
        return "long"
    if s in ("short",):
        return "short"
    return "flat"


def gate_execution(
    *,
    policy_hint: Optional[Dict[str, Any]] = None,
    dual_recommendation: Optional[Dict[str, Any]] = None,
    decision_memory: Optional[Dict[str, Any]] = None,
    risk_veto: Optional[Dict[str, Any]] = None,
    session: Optional[MarketSession] = None,
    levels: Optional[TradeLevels] = None,
    overall_score: float = 50.0,
) -> ExecuteGate:
    """
    Gate execution based on risk_veto, policy, memory, session clock, and tape.
    
    Risk veto hierarchy (fail closed):
    1. Missing/invalid risk_veto → flat (fail closed for NEW risk)
    2. VETO → flat, risk = 0
    3. CUT → keep long only if policy says long; use risk_veto.risk_pct (if null → flat)
    4. ALLOW → still apply clock/tape/policy/memory gates
    
    Args:
        policy_hint: Policy hint dict with action, conviction, rationale
        dual_recommendation: Dual research/execute labels
        decision_memory: Memory dict (from memory.apply_to_policy_inputs)
        risk_veto: Risk veto object (decision, reason, missing, risk_pct)
        session: Market session status
        levels: Trade levels with tape validity
    
    Returns:
        ExecuteGate with final action and reasons
    """
    reasons: List[str] = []
    
    # Extract policy_hint action and risk
    policy_action = None
    policy_risk_pct = None
    if policy_hint and isinstance(policy_hint, dict):
        policy_action = normalize_action(policy_hint.get("action"))
        policy_risk_pct = policy_hint.get("suggested_risk_pct")
    
    # Extract dual recommendation labels
    research_label = None
    dual_execute_label = None
    if dual_recommendation and isinstance(dual_recommendation, dict):
        research_label = dual_recommendation.get("research_recommendation")
        dual_execute_label = dual_recommendation.get("execution_label")
    
    # Start with policy_hint action (or dual execute label as fallback)
    if policy_action:
        proposed_action = policy_action
        reasons.append(f"policy_hint: {policy_action}")
    elif dual_execute_label:
        proposed_action = normalize_action(dual_execute_label)
        reasons.append(f"dual Execute: {dual_execute_label}")
    else:
        proposed_action = "flat"
        reasons.append("no policy_hint or dual Execute - default flat")
    
    # ========================================================================
    # GATE 0: Risk veto (FIRST GATE - fail closed)
    # ========================================================================
    risk_veto_decision = None
    risk_veto_blocks = False
    final_risk_pct = policy_risk_pct  # Default to policy risk
    
    if not _is_valid_risk_veto(risk_veto):
        # Missing or invalid risk_veto → fail closed (flat for NEW risk)
        risk_veto_blocks = True
        reasons.append("risk_veto: missing or invalid - fail closed (flat for NEW risk)")
        return ExecuteGate(
            would_be_flat=True,
            execute_action="flat",
            final_risk_pct=0.0,
            reasons=reasons,
            policy_hint_action=policy_action,
            dual_execute_label=dual_execute_label,
            research_label=research_label,
            risk_veto_decision=None,
            risk_veto_blocks=True,
            memory_blocks=False,
            session_blocks=False,
            tape_blocks=False,
            policy_conflict=_is_policy_conflict(research_label, "flat"),
        )
    
    risk_veto_decision = str(risk_veto.get("decision", "")).upper()
    risk_veto_reason = risk_veto.get("reason", "")
    risk_veto_risk_pct = risk_veto.get("risk_pct")
    
    reasons.append(f"risk_veto: {risk_veto_decision}")
    
    # Branch on risk_veto.decision
    if risk_veto_decision == "VETO":
        # VETO → stay flat, risk = 0
        risk_veto_blocks = True
        reasons.append(f"risk_veto VETO: {risk_veto_reason}")
        return ExecuteGate(
            would_be_flat=True,
            execute_action="flat",
            final_risk_pct=0.0,
            reasons=reasons,
            policy_hint_action=policy_action,
            dual_execute_label=dual_execute_label,
            research_label=research_label,
            risk_veto_decision=risk_veto_decision,
            risk_veto_blocks=True,
            memory_blocks=False,
            session_blocks=False,
            tape_blocks=False,
            policy_conflict=_is_policy_conflict(research_label, "flat"),
        )
    
    elif risk_veto_decision == "CUT":
        # CUT → keep long only if policy says long; use risk_veto.risk_pct
        if risk_veto_risk_pct is None or not _is_finite(risk_veto_risk_pct):
            # CUT with null/invalid risk_pct → fail closed (flat)
            risk_veto_blocks = True
            reasons.append(f"risk_veto CUT with null/invalid risk_pct: {risk_veto_reason} - flat")
            return ExecuteGate(
                would_be_flat=True,
                execute_action="flat",
                final_risk_pct=0.0,
                reasons=reasons,
                policy_hint_action=policy_action,
                dual_execute_label=dual_execute_label,
                research_label=research_label,
                risk_veto_decision=risk_veto_decision,
                risk_veto_blocks=True,
                memory_blocks=False,
                session_blocks=False,
                tape_blocks=False,
                policy_conflict=_is_policy_conflict(research_label, "flat"),
            )
        
        # CUT with valid risk_pct: override policy risk, but still need policy to be constructive
        final_risk_pct = float(risk_veto_risk_pct)
        reasons.append(f"risk_veto CUT: {risk_veto_reason} - risk_pct={final_risk_pct}")
        # Continue to other gates (will check if policy is constructive)
    
    elif risk_veto_decision == "ALLOW":
        # ALLOW → still apply all other gates
        reasons.append(f"risk_veto ALLOW: {risk_veto_reason} - proceed to other gates")
        # Continue to other gates
    
    else:
        # Unknown decision → fail closed
        risk_veto_blocks = True
        reasons.append(f"risk_veto unknown decision '{risk_veto_decision}' - fail closed")
        return ExecuteGate(
            would_be_flat=True,
            execute_action="flat",
            final_risk_pct=0.0,
            reasons=reasons,
            policy_hint_action=policy_action,
            dual_execute_label=dual_execute_label,
            research_label=research_label,
            risk_veto_decision=risk_veto_decision,
            risk_veto_blocks=True,
            memory_blocks=False,
            session_blocks=False,
            tape_blocks=False,
            policy_conflict=_is_policy_conflict(research_label, "flat"),
        )
    
    # ========================================================================
    # From here: risk_veto is ALLOW or CUT (with valid risk_pct)
    # Apply remaining gates
    # ========================================================================
    
    # Gate 1: Policy already flat
    if proposed_action == "flat":
        reasons.append("Policy already flat - no execution")
        return ExecuteGate(
            would_be_flat=True,
            execute_action="flat",
            final_risk_pct=0.0,
            reasons=reasons,
            policy_hint_action=policy_action,
            dual_execute_label=dual_execute_label,
            research_label=research_label,
            risk_veto_decision=risk_veto_decision,
            risk_veto_blocks=False,
            memory_blocks=False,
            session_blocks=False,
            tape_blocks=False,
            policy_conflict=_is_policy_conflict(research_label, proposed_action),
        )
    
    # From here: proposed_action is long or short (constructive)
    # Apply gates in order: memory, session, tape
    
    blocks = []
    memory_blocks = False
    session_blocks = False
    tape_blocks = False
    
    # Gate 2: Memory block (stop cooldown, loss streak, etc.)
    if decision_memory and isinstance(decision_memory, dict):
        if decision_memory.get("block_new_long") and proposed_action == "long":
            memory_blocks = True
            flags = ", ".join(decision_memory.get("flags") or []) or "memory cooldown"
            blocks.append(f"memory block: {flags}")
            reasons.append(f"memory block: {flags}")
    
    # Gate 3: Session clock (market closed → no new risk)
    if session:
        if not session.allows_new_trades:
            session_blocks = True
            blocks.append(f"session closed: {session.reason}")
            reasons.append(f"session gate: {session.reason}")
    else:
        # No session provided → check now
        from .session_clock import get_session_state
        session = get_session_state()
        if not session.allows_new_trades:
            session_blocks = True
            blocks.append(f"session closed: {session.reason}")
            reasons.append(f"session gate: {session.reason}")
    
    # Gate 4: Tape quality (missing or stale price)
    if levels:
        if not levels.tape_valid:
            tape_blocks = True
            blocks.append(f"tape invalid: {levels.reason}")
            reasons.append(f"tape gate: {levels.reason}")
    else:
        # No levels provided → assume tape missing
        tape_blocks = True
        blocks.append("tape missing: no levels computed")
        reasons.append("tape gate: no levels computed")
    
    # Final decision
    if blocks:
        final_action = "flat"
        would_be_flat = True
        final_risk_pct = 0.0
        reasons.append(f"Execute gated to FLAT: {len(blocks)} blocker(s)")
    else:
        final_action = proposed_action
        would_be_flat = False
        reasons.append(f"All gates pass - execute {final_action}")
    
    policy_conflict = _is_policy_conflict(research_label, final_action)
    if policy_conflict:
        reasons.append(f"policy_conflict: Research {research_label} but Execute {final_action}")
    
    return ExecuteGate(
        would_be_flat=would_be_flat,
        execute_action=final_action,
        final_risk_pct=final_risk_pct if not would_be_flat else 0.0,
        reasons=reasons,
        policy_hint_action=policy_action,
        dual_execute_label=dual_execute_label,
        research_label=research_label,
        risk_veto_decision=risk_veto_decision,
        risk_veto_blocks=risk_veto_blocks,
        memory_blocks=memory_blocks,
        session_blocks=session_blocks,
        tape_blocks=tape_blocks,
        policy_conflict=policy_conflict,
    )


def _is_valid_risk_veto(risk_veto: Optional[Dict[str, Any]]) -> bool:
    """
    Check if risk_veto is valid (non-missing, has decision field).
    
    Returns False if:
    - risk_veto is None or not a dict
    - decision field is missing or not a valid string
    """
    if not risk_veto or not isinstance(risk_veto, dict):
        return False
    decision = risk_veto.get("decision")
    if not decision or not isinstance(decision, str):
        return False
    return str(decision).upper() in ("ALLOW", "CUT", "VETO")


def _is_finite(val: Any) -> bool:
    """Check if value is a finite number."""
    try:
        f = float(val)
        return not (f != f or f == float('inf') or f == float('-inf'))  # NaN or inf check
    except (TypeError, ValueError):
        return False


def _is_policy_conflict(research_label: Optional[str], execute_action: str) -> bool:
    """Check if research is constructive but execution is flat."""
    if not research_label:
        return False
    r = str(research_label).upper()
    research_bull = r in ("BUY", "STRONG_BUY")
    exec_not_long = execute_action != "long"
    return research_bull and exec_not_long
