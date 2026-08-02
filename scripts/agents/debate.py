"""
Multi-turn bull/bear debate session helpers.

Used by Grok Build orchestration (stock-decision skill) and optional CLI.
Pure Python — no LLM calls. History is injected into agent prompts.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_MAX_ROUNDS = 2  # each round = Bull turn + Bear turn
SCHEMA_VERSION = "1.0.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class DebateSession:
    """
    Ordered multi-turn debate transcript.

    Round n contains optional bull + bear messages (a full round is complete
    when both sides have spoken for that round index).
    """

    def __init__(
        self,
        ticker: str,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        handoff_path: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ):
        self.ticker = str(ticker).upper()
        self.max_rounds = max(1, int(max_rounds))
        self.handoff_path = handoff_path
        self.meta = dict(meta or {})
        self.created_at = _now_iso()
        self.updated_at = self.created_at
        self.turns: List[Dict[str, Any]] = []
        self.manager_plan: Optional[str] = None
        self.trader_proposal: Optional[str] = None
        self.final_decision: Optional[Dict[str, Any]] = None
        self.status: str = "open"  # open | debating | manager | trader | closed

    # ── mutation ────────────────────────────────────────────────────────────

    def append_turn(
        self,
        role: str,
        content: str,
        round_num: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Append a speaker turn. role: bull | bear | manager | trader | system
        round_num: 1-based for bull/bear; auto-inferred if omitted.
        """
        role_n = str(role or "").strip().lower()
        if role_n in ("bull analyst", "bull_researcher"):
            role_n = "bull"
        if role_n in ("bear analyst", "bear_researcher"):
            role_n = "bear"
        if role_n not in ("bull", "bear", "manager", "trader", "system"):
            raise ValueError(f"invalid debate role: {role!r}")

        text = (content or "").strip()
        if not text:
            raise ValueError("empty debate content")

        if role_n in ("bull", "bear"):
            if round_num is None:
                round_num = self._infer_next_round(role_n)
            round_num = int(round_num)
            if round_num < 1 or round_num > self.max_rounds:
                raise ValueError(
                    f"round_num {round_num} out of range 1..{self.max_rounds}"
                )
        else:
            round_num = round_num  # may be None for manager/trader

        turn = {
            "seq": len(self.turns) + 1,
            "role": role_n,
            "round": round_num,
            "content": text,
            "at": _now_iso(),
        }
        self.turns.append(turn)
        self.updated_at = turn["at"]
        if role_n in ("bull", "bear"):
            self.status = "debating"
        elif role_n == "manager":
            self.manager_plan = text
            self.status = "manager"
        elif role_n == "trader":
            self.trader_proposal = text
            self.status = "trader"
        return turn

    def set_final_decision(self, decision: Dict[str, Any]) -> None:
        self.final_decision = deepcopy(decision) if decision else None
        self.status = "closed"
        self.updated_at = _now_iso()

    # ── queries ─────────────────────────────────────────────────────────────

    def _infer_next_round(self, role: str) -> int:
        """Next round index for bull/bear based on history."""
        for r in range(1, self.max_rounds + 1):
            roles = {t["role"] for t in self.turns if t.get("round") == r and t["role"] in ("bull", "bear")}
            if role not in roles:
                return r
        return self.max_rounds

    def bull_bear_turn_count(self) -> int:
        return sum(1 for t in self.turns if t["role"] in ("bull", "bear"))

    def completed_rounds(self) -> int:
        """Rounds where both bull and bear have spoken."""
        n = 0
        for r in range(1, self.max_rounds + 1):
            roles = {t["role"] for t in self.turns if t.get("round") == r}
            if "bull" in roles and "bear" in roles:
                n += 1
        return n

    def debate_complete(self) -> bool:
        return self.completed_rounds() >= self.max_rounds

    def next_speaker(self) -> Optional[str]:
        """
        Who should speak next in the bull/bear phase.
        Returns 'bull' | 'bear' | 'manager' | None (if already past debate).
        """
        if self.status in ("manager", "trader", "closed"):
            return None
        if self.debate_complete():
            return "manager"
        # Find first incomplete round
        for r in range(1, self.max_rounds + 1):
            roles = {t["role"] for t in self.turns if t.get("round") == r and t["role"] in ("bull", "bear")}
            if "bull" not in roles:
                return "bull"
            if "bear" not in roles:
                return "bear"
        return "manager"

    def last_argument(self, role: str) -> Optional[str]:
        role_n = role.lower()
        for t in reversed(self.turns):
            if t["role"] == role_n:
                return t["content"]
        return None

    def history_text(self, max_chars: int = 12_000) -> str:
        """Format full transcript for injection into agent prompts."""
        if not self.turns:
            return "(no debate history yet)"
        lines: List[str] = [
            f"# Debate transcript — {self.ticker}",
            f"max_rounds={self.max_rounds} completed={self.completed_rounds()} status={self.status}",
            "",
        ]
        for t in self.turns:
            label = {
                "bull": "Bull Analyst",
                "bear": "Bear Analyst",
                "manager": "Research Manager",
                "trader": "Trader",
                "system": "System",
            }.get(t["role"], t["role"])
            rnd = f" [round {t['round']}]" if t.get("round") else ""
            lines.append(f"### {label}{rnd} (seq {t['seq']})")
            lines.append(t["content"].rstrip())
            lines.append("")
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[: max_chars - 20] + "\n\n…[truncated]"
        return text

    def injection_bundle(self) -> Dict[str, Any]:
        """Fields ready for prompt placeholders."""
        return {
            "ticker": self.ticker,
            "max_rounds": self.max_rounds,
            "completed_rounds": self.completed_rounds(),
            "debate_complete": self.debate_complete(),
            "next_speaker": self.next_speaker(),
            "debate_history": self.history_text(),
            "bull_last_argument": self.last_argument("bull"),
            "bear_last_argument": self.last_argument("bear"),
            "status": self.status,
        }

    # ── serialization ───────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ticker": self.ticker,
            "max_rounds": self.max_rounds,
            "handoff_path": self.handoff_path,
            "meta": self.meta,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "completed_rounds": self.completed_rounds(),
            "turns": list(self.turns),
            "manager_plan": self.manager_plan,
            "trader_proposal": self.trader_proposal,
            "final_decision": self.final_decision,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DebateSession":
        sess = cls(
            ticker=data.get("ticker") or "UNKNOWN",
            max_rounds=int(data.get("max_rounds") or DEFAULT_MAX_ROUNDS),
            handoff_path=data.get("handoff_path"),
            meta=data.get("meta") or {},
        )
        sess.created_at = data.get("created_at") or sess.created_at
        sess.updated_at = data.get("updated_at") or sess.updated_at
        sess.turns = list(data.get("turns") or [])
        sess.manager_plan = data.get("manager_plan")
        sess.trader_proposal = data.get("trader_proposal")
        sess.final_decision = data.get("final_decision")
        sess.status = data.get("status") or "open"
        return sess

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return path

    @classmethod
    def load(cls, path: str) -> "DebateSession":
        with open(path) as f:
            return cls.from_dict(json.load(f))


def default_debate_path(repo_root: str, ticker: str, ts: Optional[str] = None) -> str:
    t = (ts or _ts_slug())
    return os.path.join(repo_root, "decisions", f"debate_{ticker.upper()}_{t}.json")


def extract_role_prefix(text: str) -> Optional[str]:
    """Detect 'Bull Analyst:' / 'Bear Analyst:' prefix."""
    if not text:
        return None
    m = re.match(r"^\s*(Bull|Bear)\s+Analyst\s*:", text, re.I)
    if not m:
        return None
    return m.group(1).lower()


def validate_turn_grounding(
    content: str,
    allowed_numbers: Optional[List[float]] = None,
    max_novel: int = 8,
) -> Tuple[bool, List[str]]:
    """
    Lightweight check: warn if many numeric tokens appear that are not in
    allowed_numbers (from handoff). Soft validation — does not hard-fail debate.
    """
    warnings: List[str] = []
    if not content:
        return True, ["empty content"]
    nums = re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", content)
    if allowed_numbers is None:
        return True, warnings
    allowed = {round(float(x), 4) for x in allowed_numbers if x is not None}
    novel = []
    for n in nums:
        try:
            v = round(float(n), 4)
        except ValueError:
            continue
        # ignore pure integers that look like years / round numbers in prose
        if v in allowed or v in (1, 2, 3, 5, 10, 20, 50, 100):
            continue
        novel.append(v)
    if len(set(novel)) > max_novel:
        warnings.append(
            f"many numbers not in handoff allow-list ({len(set(novel))} novel); re-check grounding"
        )
    return len(warnings) == 0, warnings
