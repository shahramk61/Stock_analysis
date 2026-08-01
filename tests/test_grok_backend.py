"""Tests for Grok client helpers and decision schema (no live API required)."""
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agents.decision_schema import (  # noqa: E402
    normalize_decision,
    validate_decision,
    parse_decision_from_text,
    normalize_action,
    build_handoff_bundle,
)
from agents.llm.grok_client import grok_available, GrokLLM  # noqa: E402


def test_normalize_action():
    assert normalize_action("BUY") == "long"
    assert normalize_action("HOLD") == "flat"
    assert normalize_action("SELL") == "flat"


def test_validate_decision_ok():
    d = normalize_decision({
        "ticker": "aapl",
        "action": "BUY",
        "conviction": "High",
        "rationale": "Score 72 with High conviction and acceptable VaR in handoff.",
        "overall_score": 72,
    })
    assert d["action"] == "long"
    assert d["conviction"] == "High"
    assert d["schema_valid"] is True
    assert d["backend"] == "grok-build"


def test_validate_decision_missing():
    ok, errs = validate_decision({"ticker": "X"})
    assert not ok
    assert any("missing" in e for e in errs)


def test_parse_final_proposal():
    text = """
    Some plan...
    FINAL TRANSACTION PROPOSAL: **HOLD**
    """
    d = parse_decision_from_text(text, ticker="TSLA")
    assert d["action"] == "flat"
    assert d["ticker"] == "TSLA"


def test_parse_json_fence():
    text = '''
```json
{"ticker": "MSFT", "action": "long", "conviction": "Medium", "rationale": "Bullish consensus and score 68 in handoff."}
```
'''
    d = parse_decision_from_text(text, ticker="MSFT")
    assert d["action"] == "long"
    assert d["schema_valid"] is True


def test_handoff_bundle_shape():
    b = build_handoff_bundle(ticker="nvda", signals={"overall_score": 55}, quant={"quantitative_conviction": "Low"})
    assert b["ticker"] == "NVDA"
    assert "invent" in b["backend_note"].lower() or "Do not invent" in b["backend_note"]


def test_grok_available_without_key():
    # Should not throw
    _ = grok_available()


def test_grok_llm_requires_key():
    old = os.environ.pop("XAI_API_KEY", None)
    try:
        try:
            GrokLLM(api_key="")
            assert False, "should require key"
        except RuntimeError:
            pass
    finally:
        if old is not None:
            os.environ["XAI_API_KEY"] = old


if __name__ == "__main__":
    test_normalize_action()
    test_validate_decision_ok()
    test_validate_decision_missing()
    test_parse_final_proposal()
    test_parse_json_fence()
    test_handoff_bundle_shape()
    test_grok_available_without_key()
    test_grok_llm_requires_key()
    print("All grok backend tests passed.")
