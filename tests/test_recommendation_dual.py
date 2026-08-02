"""Dual research vs execute recommendation labels."""
import os
import sys

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from recommendation import (  # noqa: E402
    dual_recommendation,
    research_recommendation,
    research_vs_execution_conflict,
)


def test_research_bands():
    assert research_recommendation(80) == "STRONG_BUY"
    assert research_recommendation(64.9) == "BUY"
    assert research_recommendation(55) == "HOLD"
    assert research_recommendation(40) == "CAUTION"
    assert research_recommendation(20) == "SELL"


def test_gme_style_dual_conflict():
    d = dual_recommendation(
        64.9,
        policy_action="flat",
        policy_conviction="Low",
        suggested_risk_pct=0.0,
        policy_rationale="VaR high → flat",
    )
    assert d["research_recommendation"] == "BUY"
    assert d["execution_action"] == "flat"
    assert d["execution_label"] == "FLAT"
    assert d["policy_conflict"] is True
    assert "Research BUY" in d["recommendation"]
    assert "Execute FLAT" in d["recommendation"]
    assert research_vs_execution_conflict("BUY", "flat") is True
    assert research_vs_execution_conflict("BUY", "long") is False


def test_aligned_long_no_conflict():
    d = dual_recommendation(72.0, policy_action="long", policy_conviction="High", suggested_risk_pct=0.01)
    assert d["research_recommendation"] == "BUY"
    assert d["execution_label"] == "LONG"
    assert d["policy_conflict"] is False


if __name__ == "__main__":
    test_research_bands()
    test_gme_style_dual_conflict()
    test_aligned_long_no_conflict()
    print("All dual recommendation tests passed.")
