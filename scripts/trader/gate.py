"""
Execute gate: combine policy_hint, dual_recommendation, decision memory, 
session clock, and tape quality.

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
    Execute gating decision combining all timing/tape/memory factors.
    
    would_be_flat: True if any gate blocks execution
    execute_action: final action after all gates applied
    reasons: list of reasons for the decision
    """
    would_be_flat: bool
    execute_action: str  # "long", "flat", "short"
    reasons: List[str]
    
    # Component states
    policy_hint_action: Optional[str] = None
    dual_execute_label: Optional[str] = None
    research_label: Optional[str] = None
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
    session: Optional[MarketSession] = None,
    levels: Optional[TradeLevels] = None,
    overall_score: float = 50.0,
) -> ExecuteGate:
    """
    Gate execution based on policy, memory, session clock, and tape.
    
    Args:
        policy_hint: Policy hint dict with action, conviction, rationale
        dual_recommendation: Dual research/execute labels
        decision_memory: Memory dict (from memory.apply_to_policy_inputs)
        session: Market session status
        levels: Trade levels with tape validity
    
    Returns:
        ExecuteGate with final action and reasons
    """
    reasons: List[str] = []
    
    # Extract policy_hint action
    policy_action = None
    if policy_hint and isinstance(policy_hint, dict):
        policy_action = normalize_action(policy_hint.get("action"))
    
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
    
    # Gate 1: Policy already flat
    if proposed_action == "flat":
        reasons.append("Policy already flat - no execution")
        return ExecuteGate(
            would_be_flat=True,
            execute_action="flat",
            reasons=reasons,
            policy_hint_action=policy_action,
            dual_execute_label=dual_execute_label,
            research_label=research_label,
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
        reasons=reasons,
        policy_hint_action=policy_action,
        dual_execute_label=dual_execute_label,
        research_label=research_label,
        memory_blocks=memory_blocks,
        session_blocks=session_blocks,
        tape_blocks=tape_blocks,
        policy_conflict=policy_conflict,
    )


def _is_policy_conflict(research_label: Optional[str], execute_action: str) -> bool:
    """Check if research is constructive but execution is flat."""
    if not research_label:
        return False
    r = str(research_label).upper()
    research_bull = r in ("BUY", "STRONG_BUY")
    exec_not_long = execute_action != "long"
    return research_bull and exec_not_long
