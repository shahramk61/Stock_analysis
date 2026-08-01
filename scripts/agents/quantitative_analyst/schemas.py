"""
JSON schemas and validators for Quantitative Analyst structured outputs.

Downstream agents (Researchers, Trader, Risk, backtest policy) must consume
these canonical keys — never re-parse free-form markdown for metrics.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple


CONVICTION_LABELS = ("High", "Medium", "Low", "Unknown")

# Canonical JSON Schema (draft-style) for documentation + optional jsonschema lib
QUANTITATIVE_SIGNALS_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "QuantitativeSignals",
    "type": "object",
    "additionalProperties": True,
    "required": [
        "ticker",
        "conviction",
        "raw_conviction_score",
        "multi_horizon",
        "risk",
        "regime",
    ],
    "properties": {
        "ticker": {"type": "string", "minLength": 1},
        "conviction": {"type": "string", "enum": list(CONVICTION_LABELS)},
        "raw_conviction_score": {"type": ["integer", "number"]},
        "multi_horizon": {
            "type": "object",
            "properties": {
                "horizons": {"type": "object"},
                "consensus_direction": {"type": "string"},
                "trend_signal": {"type": "string"},
                "model_disagreement": {},
            },
        },
        "risk": {
            "type": "object",
            "properties": {
                "var_95": {"type": ["number", "integer"]},
                "cvar_95": {"type": ["number", "integer"]},
                "simulated_annual_vol": {"type": ["number", "integer"]},
                "risk_level": {"type": "string"},
            },
        },
        "regime": {
            "type": "object",
            "properties": {
                "regime": {"type": "string"},
                "probs": {"type": "array"},
            },
        },
        "quality": {"type": "object"},
        "momentum": {"type": "object"},
        "liquidity_flow": {"type": "object"},
        "beta": {"type": "object"},
        "earnings_surprise": {"type": ["number", "integer", "null"]},
        "garch": {"type": "object"},
        "atr": {"type": "object"},
        "classic": {"type": "object"},
        "trend": {"type": "object"},
        "adx": {"type": "object"},
        "x_sentiment": {"type": "object"},
        "schema_version": {"type": "string"},
        "schema_valid": {"type": "boolean"},
        "schema_errors": {"type": "array", "items": {"type": "string"}},
    },
}

QUANT_NODE_OUTPUT_SCHEMA: Dict[str, Any] = {
    "title": "QuantitativeAnalystNodeOutput",
    "type": "object",
    "required": [
        "quantitative_report",
        "quantitative_conviction",
        "quantitative_signals",
        "quantitative_warnings",
        "quantitative_debate_commentary",
    ],
    "properties": {
        "quantitative_report": {"type": "string"},
        "quantitative_conviction": {"type": "string", "enum": list(CONVICTION_LABELS)},
        "quantitative_signals": QUANTITATIVE_SIGNALS_SCHEMA,
        "quantitative_warnings": {"type": "array", "items": {"type": "string"}},
        "quantitative_debate_commentary": {"type": "string"},
        "messages": {"type": "array"},
    },
}

SCHEMA_VERSION = "1.0.0"


def normalize_conviction(label: Any) -> str:
    s = str(label or "Unknown").strip()
    # Strip soft language; map to enum only
    low = s.lower()
    if "high" in low and "low" not in low:
        return "High"
    if "low" in low:
        return "Low"
    if "med" in low or "neutral" in low or "balanced" in low:
        return "Medium"
    if s in CONVICTION_LABELS:
        return s
    return "Unknown"


def validate_quantitative_signals(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Lightweight schema check (no external deps). Returns (ok, errors)."""
    errors: List[str] = []
    if not isinstance(payload, dict):
        return False, ["signals payload is not an object"]

    for key in ("ticker", "conviction", "raw_conviction_score", "multi_horizon", "risk", "regime"):
        if key not in payload:
            errors.append(f"missing required key: {key}")

    if "ticker" in payload and (not isinstance(payload["ticker"], str) or not payload["ticker"].strip()):
        errors.append("ticker must be a non-empty string")

    if "conviction" in payload:
        conv = payload["conviction"]
        if conv not in CONVICTION_LABELS:
            errors.append(f"conviction must be one of {CONVICTION_LABELS}, got {conv!r}")

    if "raw_conviction_score" in payload:
        try:
            float(payload["raw_conviction_score"])
        except (TypeError, ValueError):
            errors.append("raw_conviction_score must be numeric")

    for nest in ("multi_horizon", "risk", "regime"):
        if nest in payload and payload[nest] is not None and not isinstance(payload[nest], dict):
            errors.append(f"{nest} must be an object")

    risk = payload.get("risk") or {}
    if isinstance(risk, dict) and "var_95" in risk and risk["var_95"] is not None:
        try:
            float(risk["var_95"])
        except (TypeError, ValueError):
            errors.append("risk.var_95 must be numeric when present")

    regime = payload.get("regime") or {}
    if isinstance(regime, dict) and "regime" in regime:
        if not isinstance(regime["regime"], str):
            errors.append("regime.regime must be a string")

    # Optional: try jsonschema if installed
    try:
        import jsonschema  # type: ignore
        jsonschema.validate(payload, QUANTITATIVE_SIGNALS_SCHEMA)
    except ImportError:
        pass
    except Exception as e:
        errors.append(f"jsonschema: {str(e)[:160]}")

    return len(errors) == 0, errors


def normalize_quantitative_signals(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy with conviction normalized and schema metadata attached."""
    out = deepcopy(payload) if isinstance(payload, dict) else {}
    out["conviction"] = normalize_conviction(out.get("conviction"))
    if "raw_conviction_score" in out:
        try:
            out["raw_conviction_score"] = int(out["raw_conviction_score"])
        except (TypeError, ValueError):
            out["raw_conviction_score"] = 3
    out.setdefault("ticker", "UNKNOWN")
    out.setdefault("multi_horizon", {"horizons": {}, "consensus_direction": "Neutral", "trend_signal": "Stable"})
    out.setdefault("risk", {})
    out.setdefault("regime", {"regime": "Neutral"})
    out["schema_version"] = SCHEMA_VERSION
    ok, errs = validate_quantitative_signals(out)
    out["schema_valid"] = ok
    out["schema_errors"] = errs
    return out


def extract_grounded_numbers(*texts: str) -> List[str]:
    """Extract numeric tokens used for LLM debate integrity checks."""
    found: List[str] = []
    for t in texts:
        if not t:
            continue
        # percentages, decimals, integers (keep distinctive values)
        for m in re.findall(r"-?\d+\.?\d*%?", str(t)):
            if m not in found:
                found.append(m)
    return found


def debate_preserves_numbers(facts: str, rewritten: str, required: Optional[List[str]] = None) -> bool:
    """
    Reject LLM rewrites that drop key grounded numbers from the facts block.
    Required tokens default to distinctive numbers from facts (len>=2 or with %).
    """
    if not rewritten or not rewritten.strip():
        return False
    req = required
    if req is None:
        candidates = extract_grounded_numbers(facts)
        req = [n for n in candidates if len(n) >= 2 or n.endswith("%")]
        # Keep at most 12 anchors so minor formatting changes don't fail everything
        req = req[:12]
    if not req:
        return True
    # At least 70% of required anchors must appear in the rewrite
    hits = sum(1 for n in req if n in rewritten)
    return hits >= max(1, int(0.7 * len(req)))


def llm_rephrase_debate(llm: Any, facts_block: str) -> Tuple[str, List[str]]:
    """
    Optional LLM phrasing layer. Returns (text, warnings).
    On any integrity failure, returns the original facts_block.
    """
    warnings: List[str] = []
    if llm is None:
        return facts_block, warnings

    prompt = (
        "You rephrase a FACTS-ONLY Quantitative Analyst brief for a bull/bear researcher debate.\n"
        "HARD RULES:\n"
        "1. Do NOT invent any numbers, tickers, metrics, or claims not present in the facts.\n"
        "2. Keep every numeric value exactly as written (VaR, momentum %, IVR, scores, etc.).\n"
        "3. Do not change the conviction label (High/Medium/Low) or regime label.\n"
        "4. You may only improve clarity, structure, and debate framing.\n"
        "5. If unsure, copy the facts verbatim.\n\n"
        f"FACTS:\n{facts_block}\n"
    )
    try:
        if hasattr(llm, "invoke"):
            out = llm.invoke(prompt)
            text = getattr(out, "content", None) or str(out)
        elif callable(llm):
            out = llm(prompt)
            text = getattr(out, "content", None) or str(out)
        else:
            warnings.append("llm: unsupported interface; using facts template")
            return facts_block, warnings

        text = str(text).strip()
        if not debate_preserves_numbers(facts_block, text):
            warnings.append("llm: rewrite dropped grounded numbers — rejected, using facts template")
            return facts_block, warnings
        # Conviction label must still appear
        for label in ("High", "Medium", "Low"):
            if f"conviction {label}" in facts_block.lower().replace("conviction:", "conviction "):
                break
        # Soft check: if facts mention conviction X, rewrite should too
        m = re.search(r"conviction\s+(High|Medium|Low)", facts_block, re.I)
        if m and m.group(1).lower() not in text.lower():
            warnings.append("llm: conviction label missing in rewrite — rejected")
            return facts_block, warnings
        return text, warnings
    except Exception as e:
        warnings.append(f"llm: {str(e)[:100]}")
        return facts_block, warnings
