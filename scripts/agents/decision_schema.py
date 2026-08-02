"""
Schema for Grok Build / agent final trading decisions.

Pipeline scores are ground truth; this schema validates the *decision* artifact
produced by Grok agents after reading injected facts.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from agents.quantitative_analyst.schemas import (
        CONVICTION_LABELS,
        normalize_conviction,
        extract_grounded_numbers,
    )
except ImportError:
    from quantitative_analyst.schemas import (  # type: ignore
        CONVICTION_LABELS,
        normalize_conviction,
        extract_grounded_numbers,
    )

ACTIONS = ("long", "flat", "short", "buy", "hold", "sell")

DECISION_SCHEMA: Dict[str, Any] = {
    "title": "StockAgentDecision",
    "type": "object",
    "required": ["ticker", "action", "conviction", "rationale"],
    "properties": {
        "ticker": {"type": "string"},
        "action": {"type": "string", "enum": list(ACTIONS)},
        "conviction": {"type": "string", "enum": list(CONVICTION_LABELS)},
        "rationale": {"type": "string"},
        "suggested_risk_pct": {"type": ["number", "null"]},
        "stop_price": {"type": ["number", "null"]},
        "overall_score": {"type": ["number", "null"]},
        "pipeline_refs": {"type": "array", "items": {"type": "string"}},
        "policy_conflict": {"type": ["boolean", "null"]},
        "policy_action": {"type": ["string", "null"]},
        "backend": {"type": "string"},
        "model": {"type": "string"},
        "schema_version": {"type": "string"},
        "debate_rounds": {"type": ["integer", "null"]},
        "debate_path": {"type": ["string", "null"]},
        "early_stop": {"type": ["boolean", "null"]},
    },
}

SCHEMA_VERSION = "1.0.0"

_ACTION_MAP = {
    "buy": "long",
    "long": "long",
    "hold": "flat",
    "flat": "flat",
    "sell": "flat",  # long-only policy maps sell → flat exit intent
    "short": "short",
}


def normalize_action(action: Any) -> str:
    s = str(action or "flat").strip().lower()
    return _ACTION_MAP.get(s, "flat")


def validate_decision(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["decision is not an object"]
    for k in ("ticker", "action", "conviction", "rationale"):
        if k not in payload or payload[k] in (None, ""):
            errors.append(f"missing required field: {k}")
    if "action" in payload:
        a = str(payload["action"]).lower()
        if a not in ACTIONS and normalize_action(a) not in ("long", "flat", "short"):
            errors.append(f"invalid action: {payload['action']!r}")
    if "conviction" in payload:
        c = normalize_conviction(payload["conviction"])
        if c == "Unknown" and str(payload["conviction"]) not in CONVICTION_LABELS:
            errors.append(f"invalid conviction: {payload['conviction']!r}")
    if "rationale" in payload and len(str(payload["rationale"]).strip()) < 8:
        errors.append("rationale too short")
    return len(errors) == 0, errors


def normalize_decision(
    payload: Dict[str, Any],
    *,
    ticker: Optional[str] = None,
    backend: str = "grok-build",
    model: str = "grok-4.5",
) -> Dict[str, Any]:
    out = deepcopy(payload) if isinstance(payload, dict) else {}
    out["ticker"] = (ticker or out.get("ticker") or "UNKNOWN").upper()
    out["action"] = normalize_action(out.get("action"))
    out["conviction"] = normalize_conviction(out.get("conviction"))
    out["rationale"] = str(out.get("rationale") or "").strip()
    out["backend"] = out.get("backend") or backend
    out["model"] = out.get("model") or model
    out["schema_version"] = SCHEMA_VERSION
    out.setdefault("pipeline_refs", [])
    out.setdefault("suggested_risk_pct", None)
    out.setdefault("stop_price", None)
    out.setdefault("overall_score", None)
    ok, errs = validate_decision(out)
    out["schema_valid"] = ok
    out["schema_errors"] = errs
    out["created_at"] = datetime.now(timezone.utc).isoformat()
    return out


def parse_decision_from_text(text: str, ticker: str = "UNKNOWN") -> Dict[str, Any]:
    """Extract JSON decision block or FINAL TRANSACTION PROPOSAL from agent text."""
    raw = text or ""
    # Fenced json
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S | re.I)
    if m:
        try:
            return normalize_decision(json.loads(m.group(1)), ticker=ticker)
        except json.JSONDecodeError:
            pass
    # Bare JSON object with "action"
    m2 = re.search(r"\{[^{}]*\"action\"[^{}]*\}", raw, re.S | re.I)
    if m2:
        try:
            return normalize_decision(json.loads(m2.group(0)), ticker=ticker)
        except json.JSONDecodeError:
            pass
    # FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**
    m3 = re.search(
        r"FINAL TRANSACTION PROPOSAL:\s*\*?\*?(BUY|HOLD|SELL|LONG|FLAT|SHORT)\*?\*?",
        raw,
        re.I,
    )
    action = normalize_action(m3.group(1)) if m3 else "flat"
    return normalize_decision(
        {
            "ticker": ticker,
            "action": action,
            "conviction": "Medium",
            "rationale": raw.strip()[:2000] or f"Parsed proposal: {action}",
        },
        ticker=ticker,
    )


def decision_respects_handoff_numbers(
    decision: Dict[str, Any],
    handoff_text: str,
    *,
    min_ratio: float = 0.0,
) -> Tuple[bool, List[str]]:
    """
    Soft check: if decision invents a distinctive % not in handoff, warn.
    Does not require all handoff numbers appear in rationale.
    """
    warnings: List[str] = []
    rationale = str(decision.get("rationale") or "")
    # Numbers in rationale that look like invented precision
    rat_nums = set(extract_grounded_numbers(rationale))
    hand_nums = set(extract_grounded_numbers(handoff_text))
    # Flag percentages in rationale missing from handoff
    for n in rat_nums:
        if n.endswith("%") and n not in hand_nums and len(n) >= 3:
            # allow common score bands
            if n not in ("75%", "60%", "50%", "35%"):
                warnings.append(f"rationale contains % not in handoff: {n}")
    ok = len(warnings) == 0
    return ok, warnings


def build_handoff_bundle(
    *,
    ticker: str,
    signals_path: Optional[str] = None,
    signals: Optional[Dict[str, Any]] = None,
    quant: Optional[Dict[str, Any]] = None,
    memory_text: str = "",
    policy_hint: Optional[Dict[str, Any]] = None,
    dual_recommendation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Frozen facts package injected into Grok agents (measurement backend)."""
    return {
        "ticker": ticker.upper(),
        "backend_note": (
            "Numbers below come from the local Python pipeline. "
            "Do not invent prices, scores, VaR, or fundamentals. "
            "Research BUY is not an order — use policy_hint / dual_recommendation for execution."
        ),
        "signals_path": signals_path,
        "signals": signals or {},
        "quantitative": quant or {},
        "decision_memory": memory_text or "",
        "policy_hint": policy_hint or {},
        "dual_recommendation": dual_recommendation or {},
        "schema_version": SCHEMA_VERSION,
    }
