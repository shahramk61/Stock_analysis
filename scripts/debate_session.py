#!/usr/bin/env python3
"""
CLI for multi-turn debate transcripts (no LLM — orchestration helper).

Examples:
  python scripts/debate_session.py init AAPL --rounds 2 --handoff decisions/handoff_AAPL.json
  python scripts/debate_session.py status decisions/debate_AAPL_....json
  python scripts/debate_session.py next decisions/debate_AAPL_....json
  python scripts/debate_session.py append decisions/debate_AAPL_....json --role bull --file /tmp/bull.md
  python scripts/debate_session.py history decisions/debate_AAPL_....json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from agents.debate import (  # noqa: E402
    DEFAULT_MAX_ROUNDS,
    DebateSession,
    default_debate_path,
)


def _repo_root() -> str:
    return os.path.abspath(os.path.join(SCRIPTS, ".."))


def cmd_init(args: argparse.Namespace) -> int:
    root = _repo_root()
    path = args.out or default_debate_path(root, args.ticker)
    handoff = args.handoff
    if handoff and not os.path.isabs(handoff):
        handoff = os.path.join(root, handoff)
    meta = {"profile": args.profile, "risk_panel": bool(getattr(args, "risk_panel", False))}
    if handoff and os.path.exists(handoff):
        try:
            with open(handoff) as f:
                h = json.load(f)
            meta["overall_score"] = (h.get("scores") or {}).get("overall") or h.get("overall_score")
            meta["policy_hint"] = h.get("policy_hint")
            meta["dual_recommendation"] = h.get("dual_recommendation")
        except Exception as e:
            print(f"Warning: could not read handoff: {e}", file=sys.stderr)
    sess = DebateSession(
        ticker=args.ticker,
        max_rounds=args.rounds,
        handoff_path=handoff,
        meta=meta,
    )
    sess.save(path)
    print(json.dumps({"path": path, "next_speaker": sess.next_speaker(), "max_rounds": sess.max_rounds}, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    sess = DebateSession.load(args.path)
    bundle = sess.injection_bundle()
    print(json.dumps({
        "path": args.path,
        "ticker": sess.ticker,
        "status": sess.status,
        "max_rounds": sess.max_rounds,
        "completed_rounds": sess.completed_rounds(),
        "turns": len(sess.turns),
        "next_speaker": bundle["next_speaker"],
        "debate_complete": bundle["debate_complete"],
    }, indent=2))
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    sess = DebateSession.load(args.path)
    print(sess.next_speaker() or "done")
    return 0


def cmd_append(args: argparse.Namespace) -> int:
    sess = DebateSession.load(args.path)
    if args.file:
        with open(args.file) as f:
            content = f.read()
    elif args.text:
        content = args.text
    else:
        content = sys.stdin.read()
    turn = sess.append_turn(args.role, content, round_num=args.round)
    sess.save(args.path)
    print(json.dumps({
        "appended": turn,
        "next_speaker": sess.next_speaker(),
        "completed_rounds": sess.completed_rounds(),
        "status": sess.status,
    }, indent=2, default=str))
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    sess = DebateSession.load(args.path)
    print(sess.history_text(max_chars=args.max_chars))
    return 0


def cmd_bundle(args: argparse.Namespace) -> int:
    """Emit injection placeholders as JSON for agent prompts."""
    sess = DebateSession.load(args.path)
    print(json.dumps(sess.injection_bundle(), indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Multi-turn debate session helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="Create a new debate session file")
    i.add_argument("ticker")
    i.add_argument("--rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    i.add_argument("--handoff", default=None, help="Path to handoff JSON")
    i.add_argument("--profile", default="Balanced")
    i.add_argument(
        "--risk-panel",
        action="store_true",
        help="After Trader, run Aggressive/Conservative/Neutral Risk + Portfolio Manager",
    )
    i.add_argument("--out", default=None, help="Output path")
    i.set_defaults(func=cmd_init)

    s = sub.add_parser("status", help="Show session status")
    s.add_argument("path")
    s.set_defaults(func=cmd_status)

    n = sub.add_parser("next", help="Print next speaker role")
    n.add_argument("path")
    n.set_defaults(func=cmd_next)

    a = sub.add_parser("append", help="Append a turn (text/--file/stdin)")
    a.add_argument("path")
    a.add_argument(
        "--role",
        required=True,
        choices=[
            "bull",
            "bear",
            "manager",
            "trader",
            "system",
            "risk_aggressive",
            "risk_conservative",
            "risk_neutral",
            "portfolio",
        ],
    )
    a.add_argument("--round", type=int, default=None)
    a.add_argument("--file", default=None)
    a.add_argument("--text", default=None)
    a.set_defaults(func=cmd_append)

    h = sub.add_parser("history", help="Print formatted transcript")
    h.add_argument("path")
    h.add_argument("--max-chars", type=int, default=12000)
    h.set_defaults(func=cmd_history)

    b = sub.add_parser("bundle", help="JSON injection bundle for prompts")
    b.add_argument("path")
    b.set_defaults(func=cmd_bundle)

    args = p.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
