"""
Timing card CLI and orchestrator.

Combines session clock, horizon, levels, and gate to answer:
- Is now actually a trade?
- Session vs swing
- Entry/stop/exit levels
- Would Execute be flat after timing + tape + memory?

PM book: Reads trader_snapshot.json from default path or --book-snapshot CLI flag.
Default path: /home/box/agent-data/agents/1dfbe69b-fbce-4eab-84f8-b41da3912a08/book/trader_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .session_clock import get_session_state, MarketSession, SessionState, US_EASTERN
from .horizon import choose_horizon, Horizon, HorizonChoice
from .levels import compute_levels, TradeLevels
from .gate import gate_execution, ExecuteGate


# PM trader_snapshot default path (may not exist on cloud VM)
DEFAULT_TRADER_SNAPSHOT_PATH = Path("/home/box/agent-data/agents/1dfbe69b-fbce-4eab-84f8-b41da3912a08/book/trader_snapshot.json")


@dataclass
class TimingCard:
    """
    Timing card JSON output.
    
    Answers:
    - now_a_trade: bool (session open + tape valid + gates pass)
    - session_state: str
    - horizon: "session" or "swing"
    - entry/stop/exit: nullable prices
    - execute_action: final action after gates
    - final_risk_pct: final risk % after all gates (may be from risk_veto)
    - would_be_flat: bool
    - reasons: list of decision reasons
    """
    ticker: str
    timestamp: str
    now_a_trade: bool
    session_state: str
    session_open: bool
    horizon: str
    horizon_days: Optional[int]
    entry_price: Optional[float]
    stop_price: Optional[float]
    exit_price: Optional[float]
    current_price: Optional[float]
    tape_valid: bool
    execute_action: str
    final_risk_pct: Optional[float]  # Final risk % (may be from risk_veto if CUT)
    would_be_flat: bool
    reasons: List[str]
    
    # Component details
    policy_hint_action: Optional[str] = None
    research_label: Optional[str] = None
    dual_execute_label: Optional[str] = None
    risk_veto_decision: Optional[str] = None  # ALLOW | CUT | VETO
    risk_veto_blocks: bool = False
    book_blocks: bool = False  # PM book not ready
    memory_blocks: bool = False
    session_blocks: bool = False
    tape_blocks: bool = False
    policy_conflict: bool = False
    overall_score: Optional[float] = None


def build_timing_card(
    ticker: str,
    *,
    policy_hint: Optional[Dict[str, Any]] = None,
    dual_recommendation: Optional[Dict[str, Any]] = None,
    decision_memory: Optional[Dict[str, Any]] = None,
    risk_veto: Optional[Dict[str, Any]] = None,
    book: Optional[Dict[str, Any]] = None,
    last_print: Optional[float] = None,
    current_price: Optional[float] = None,  # DEPRECATED: use last_print
    overall_score: float = 50.0,
    atr_pct: float = 0.0,
    adx: float = 0.0,
    signals: Optional[Dict[str, Any]] = None,
    execution_mode: Optional[str] = None,
    mc_risk: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,  # asof for replay
) -> TimingCard:
    """
    Build timing card from facts.
    
    Args:
        ticker: Ticker symbol
        policy_hint: Policy hint dict (action, conviction, stop_price, etc.)
        dual_recommendation: Dual research/execute labels
        decision_memory: Memory dict (from memory.apply_to_policy_inputs)
        risk_veto: Risk veto object (decision, reason, missing, risk_pct)
        book: PM book object (book_ready, starting_cash, positions, open_risk_pct)
        current_price: Current market price
        overall_score: Overall score
        atr_pct: ATR percentage
        adx: ADX value
        signals: Full signals dict
        execution_mode: Explicit "session" or "swing"
        mc_risk: Monte Carlo risk dict
        timestamp: Timestamp for session check (defaults to now)
    
    Returns:
        TimingCard with all timing/gate decisions
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    # Prefer last_print, fallback to current_price for backward compat
    price = last_print if last_print is not None else current_price
    
    # 1. Session clock (use asof/timestamp for replay, not wall-clock)
    session = get_session_state(timestamp)
    
    # 2. Horizon
    horizon_choice = choose_horizon(
        execution_mode=execution_mode,
        overall_score=overall_score,
        atr_pct=atr_pct,
        adx=adx,
        signals=signals,
    )
    
    # 3. Levels
    mc_risk_stop = None
    if mc_risk and isinstance(mc_risk, dict):
        mc_risk_stop = mc_risk.get("stop_price")
    
    policy_stop = None
    policy_target = None
    if policy_hint and isinstance(policy_hint, dict):
        policy_stop = policy_hint.get("stop_price")
        policy_target = policy_hint.get("target_price")
    
    levels = compute_levels(
        last_print=price,
        current_price=price,  # Backward compat
        policy_stop=policy_stop,
        policy_target=policy_target,
        atr_pct=atr_pct,
        mc_risk_stop=mc_risk_stop,
        horizon_tighter_stop=horizon_choice.tighter_stop,
    )
    
    # 4. Execute gate (includes risk_veto and PM book)
    gate = gate_execution(
        policy_hint=policy_hint,
        dual_recommendation=dual_recommendation,
        decision_memory=decision_memory,
        risk_veto=risk_veto,
        book=book,
        session=session,
        levels=levels,
        overall_score=overall_score,
    )
    
    # 5. Now a trade? (all must pass)
    now_a_trade = (
        session.allows_new_trades
        and levels.tape_valid
        and not gate.would_be_flat
    )
    
    # Collect all reasons
    reasons = []
    reasons.append(f"Session: {session.reason}")
    reasons.append(f"Horizon: {horizon_choice.reason}")
    if levels.tape_valid:
        reasons.append(f"Levels: {levels.reason}")
    else:
        reasons.append(f"Tape: {levels.reason}")
    reasons.extend(gate.reasons)
    
    if now_a_trade:
        reasons.append("✓ NOW A TRADE: session open, tape valid, gates pass")
    else:
        blockers = []
        if not session.allows_new_trades:
            blockers.append("session closed")
        if not levels.tape_valid:
            blockers.append("tape invalid")
        if gate.would_be_flat:
            blockers.append("gates block")
        reasons.append(f"✗ NOT A TRADE: {', '.join(blockers)}")
    
    return TimingCard(
        ticker=ticker.upper(),
        timestamp=timestamp.isoformat(),
        now_a_trade=now_a_trade,
        session_state=session.state.value,
        session_open=session.is_open,
        horizon=horizon_choice.horizon.value,
        horizon_days=horizon_choice.days,
        entry_price=levels.entry_price,
        stop_price=levels.stop_price,
        exit_price=levels.exit_price,
        current_price=levels.current_price,
        tape_valid=levels.tape_valid,
        execute_action=gate.execute_action,
        final_risk_pct=gate.final_risk_pct,
        would_be_flat=gate.would_be_flat,
        reasons=reasons,
        policy_hint_action=gate.policy_hint_action,
        research_label=gate.research_label,
        dual_execute_label=gate.dual_execute_label,
        risk_veto_decision=gate.risk_veto_decision,
        risk_veto_blocks=gate.risk_veto_blocks,
        book_blocks=gate.book_blocks,
        memory_blocks=gate.memory_blocks,
        session_blocks=gate.session_blocks,
        tape_blocks=gate.tape_blocks,
        policy_conflict=gate.policy_conflict,
        overall_score=overall_score,
    )


def load_handoff_json(path: Path) -> Dict[str, Any]:
    """Load handoff JSON from prepare_decision_handoff.py output."""
    with open(path) as f:
        return json.load(f)


def load_trader_snapshot(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Load PM trader_snapshot.json.
    
    Args:
        path: Explicit path to snapshot, or None to use default
    
    Returns:
        Snapshot dict if file exists, None otherwise (fail closed)
    """
    snapshot_path = path or DEFAULT_TRADER_SNAPSHOT_PATH
    
    if not snapshot_path.exists():
        return None
    
    try:
        with open(snapshot_path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        # File exists but can't read → fail closed
        return None


def extract_facts_from_handoff(handoff: Dict[str, Any]) -> Dict[str, Any]:
    """Extract timing-relevant facts from handoff JSON."""
    signals = handoff.get("signals") or {}
    if isinstance(signals, dict):
        signals_obj = signals
    else:
        signals_obj = {}
    
    signals_inner = signals_obj.get("signals") or {}
    
    mc_risk = signals_inner.get("mc_risk") or {}
    atr_vol = signals_inner.get("atr_vol") or {}
    adx_sig = signals_inner.get("adx") or {}
    
    policy_hint = handoff.get("policy_hint") or {}
    dual_rec = handoff.get("dual_recommendation") or {}
    risk_veto = handoff.get("risk_veto") or None
    book = handoff.get("book") or None
    
    # Memory not in handoff by default (passed as empty string)
    # Could be added from journal
    decision_memory = None
    mem_text = handoff.get("decision_memory") or ""
    if mem_text and mem_text != "":
        # If memory text is present, assume block_new_long if it mentions cooldown
        decision_memory = {
            "block_new_long": "cooldown" in mem_text.lower() or "block" in mem_text.lower(),
            "flags": ["parsed from memory_text"],
            "risk_multiplier": 1.0,
        }
    
    return {
        "ticker": handoff.get("ticker") or "UNKNOWN",
        "policy_hint": policy_hint,
        "dual_recommendation": dual_rec,
        "decision_memory": decision_memory,
        "risk_veto": risk_veto,
        "book": book,
        "current_price": handoff.get("current_price"),
        "overall_score": signals_obj.get("overall_score") or 50.0,
        "atr_pct": atr_vol.get("atr_percent") or 0.0,
        "adx": adx_sig.get("adx") or 0.0,
        "signals": signals_inner,
        "mc_risk": mc_risk,
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Trader timing CLI - answers if now is actually a trade"
    )
    parser.add_argument("ticker", help="Ticker symbol")
    parser.add_argument(
        "--handoff",
        help="Path to handoff JSON from prepare_decision_handoff.py",
    )
    parser.add_argument(
        "--asof",
        help="As-of date for replay (YYYY-MM-DD or ISO datetime). For July 2026 replay, use asof date's session (not wall-clock).",
    )
    parser.add_argument(
        "--current-price",
        type=float,
        help="[DEPRECATED] Current price - use --last-print instead",
    )
    parser.add_argument(
        "--last-print",
        type=float,
        help="Last daily Close ≤ asof (NOT live quote)",
    )
    parser.add_argument(
        "--score",
        type=float,
        default=50.0,
        help="Overall score (default 50.0)",
    )
    parser.add_argument(
        "--atr-pct",
        type=float,
        default=0.0,
        help="ATR percentage (default 0.0)",
    )
    parser.add_argument(
        "--adx",
        type=float,
        default=0.0,
        help="ADX value (default 0.0)",
    )
    parser.add_argument(
        "--execution-mode",
        "--horizon",
        dest="execution_mode",
        choices=["session", "swing", "daily"],
        help="Force session or swing/daily mode (daily = swing for replay)",
    )
    parser.add_argument(
        "--policy-action",
        help="Policy hint action (long/flat/short)",
    )
    parser.add_argument(
        "--risk-veto-decision",
        choices=["ALLOW", "CUT", "VETO"],
        help="Risk veto decision (ALLOW|CUT|VETO)",
    )
    parser.add_argument(
        "--risk-veto-risk-pct",
        type=float,
        help="Risk veto risk percentage (for CUT decision)",
    )
    parser.add_argument(
        "--risk-veto-reason",
        default="",
        help="Risk veto reason text",
    )
    parser.add_argument(
        "--book-snapshot",
        type=Path,
        help=f"Path to PM trader_snapshot.json (default: {DEFAULT_TRADER_SNAPSHOT_PATH} if exists)",
    )
    parser.add_argument(
        "--book-ready",
        action="store_true",
        help="[DEPRECATED] PM book ready flag (use --book-snapshot instead)",
    )
    parser.add_argument(
        "--starting-cash",
        type=float,
        help="[DEPRECATED] PM book starting cash (use --book-snapshot instead)",
    )
    parser.add_argument(
        "--output",
        help="Output JSON file path (prints to stdout if not specified)",
    )
    
    args = parser.parse_args()
    
    # Parse asof for replay (defaults to now)
    asof = None
    if args.asof:
        # Try date only (YYYY-MM-DD) first
        try:
            from datetime import time as dt_time
            asof_date = datetime.strptime(args.asof, "%Y-%m-%d").date()
            # Use market open time (9:30 AM ET) for date-only asof
            asof = datetime.combine(asof_date, dt_time(9, 30), tzinfo=US_EASTERN)
        except ValueError:
            # Try ISO datetime
            try:
                asof = datetime.fromisoformat(args.asof)
            except ValueError:
                print(f"Error: Invalid --asof format: {args.asof}. Use YYYY-MM-DD or ISO datetime.", file=sys.stderr)
                return 1
    
    # Load PM trader_snapshot (default path or explicit)
    book_snapshot_path = args.book_snapshot
    if book_snapshot_path is None and DEFAULT_TRADER_SNAPSHOT_PATH.exists():
        # Auto-load from default path if it exists
        book_snapshot_path = DEFAULT_TRADER_SNAPSHOT_PATH
    
    book = None
    if book_snapshot_path:
        book = load_trader_snapshot(book_snapshot_path)
        if book is None and book_snapshot_path is not None:
            print(f"Warning: Failed to load trader_snapshot from {book_snapshot_path}", file=sys.stderr)
    
    # Prefer last_print, fallback to current_price for backward compat
    price = args.last_print if args.last_print is not None else args.current_price
    
    # Load facts from handoff or CLI args
    if args.handoff:
        handoff_path = Path(args.handoff)
        if not handoff_path.exists():
            print(f"Error: handoff file not found: {handoff_path}", file=sys.stderr)
            return 1
        
        handoff = load_handoff_json(handoff_path)
        facts = extract_facts_from_handoff(handoff)
        
        # Override book from snapshot if loaded
        if book is not None:
            facts["book"] = book
        
        # CLI args can override handoff
        if price is not None:
            facts["last_print"] = price
            facts["current_price"] = price  # Backward compat
        if args.execution_mode:
            facts["execution_mode"] = args.execution_mode
        if asof is not None:
            facts["timestamp"] = asof
    else:
        # Build from CLI args
        if price is None:
            print("Error: --last-print (or --current-price) required when not using --handoff", file=sys.stderr)
            return 1
        
        # Build risk_veto from CLI args if provided
        risk_veto = None
        if args.risk_veto_decision:
            risk_veto = {
                "decision": args.risk_veto_decision,
                "reason": args.risk_veto_reason or f"CLI risk_veto: {args.risk_veto_decision}",
                "missing": [],
                "risk_pct": args.risk_veto_risk_pct,
            }
        
        # Use book from snapshot, or build deprecated simple book from CLI args
        if book is None and (args.book_ready or args.starting_cash is not None):
            # DEPRECATED: simple book from CLI args
            book = {
                "book_ready": bool(args.book_ready),
                "starting_cash": args.starting_cash,
                "positions": [],
                "open_risk_pct": None,
            }
        
        facts = {
            "ticker": args.ticker,
            "policy_hint": {"action": args.policy_action} if args.policy_action else None,
            "dual_recommendation": None,
            "decision_memory": None,
            "risk_veto": risk_veto,
            "book": book,
            "last_print": price,
            "current_price": price,  # Backward compat
            "overall_score": args.score,
            "atr_pct": args.atr_pct,
            "adx": args.adx,
            "signals": None,
            "mc_risk": None,
            "execution_mode": args.execution_mode,
            "timestamp": asof,  # For replay
        }
    
    # Build timing card
    card = build_timing_card(**facts)
    
    # Output
    output = json.dumps(asdict(card), indent=2, default=str)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Timing card written: {args.output}")
    else:
        print(output)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
