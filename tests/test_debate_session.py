"""Tests for multi-turn debate session helpers."""
import os
import sys
import tempfile

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from agents.debate import DebateSession, extract_role_prefix  # noqa: E402


def test_round_robin_and_complete():
    s = DebateSession("AAPL", max_rounds=2)
    assert s.next_speaker() == "bull"
    s.append_turn("bull", "Bull Analyst: score 63 constructive.")
    assert s.next_speaker() == "bear"
    s.append_turn("bear", "Bear Analyst: VaR elevated caution.")
    assert s.completed_rounds() == 1
    assert s.next_speaker() == "bull"
    s.append_turn("bull", "Bull Analyst: rebuttal with trend stack Bullish.")
    assert s.next_speaker() == "bear"
    s.append_turn("bear", "Bear Analyst: still flat on risk.")
    assert s.debate_complete()
    assert s.next_speaker() == "manager"
    s.append_turn("manager", "## Recommendation\nHOLD\n")
    assert s.next_speaker() == "trader"
    s.append_turn("trader", "FINAL TRANSACTION PROPOSAL: **HOLD**")
    assert s.next_speaker() is None  # no risk panel
    s.set_final_decision({"ticker": "AAPL", "action": "flat", "conviction": "Medium", "rationale": "mixed"})
    assert s.status == "closed"
    hist = s.history_text()
    assert "Bull Analyst" in hist and "Bear Analyst" in hist
    assert "round 2" in hist


def test_save_load_roundtrip():
    s = DebateSession("NVDA", max_rounds=1, handoff_path="decisions/handoff_NVDA.json")
    s.append_turn("bull", "Bull Analyst: long thesis.")
    s.append_turn("bear", "Bear Analyst: risk thesis.")
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "debate.json")
        s.save(path)
        s2 = DebateSession.load(path)
        assert s2.ticker == "NVDA"
        assert s2.completed_rounds() == 1
        assert s2.debate_complete()
        assert s2.next_speaker() == "manager"
        b = s2.injection_bundle()
        assert "debate_history" in b
        assert b["bull_last_argument"]


def test_extract_prefix():
    assert extract_role_prefix("Bull Analyst: hello") == "bull"
    assert extract_role_prefix("Bear Analyst: no") == "bear"
    assert extract_role_prefix("plain") is None


def test_risk_panel_routing():
    s = DebateSession("LLY", max_rounds=1, meta={"risk_panel": True})
    assert s.risk_panel is True
    s.append_turn("bull", "Bull Analyst: long case.")
    s.append_turn("bear", "Bear Analyst: caution.")
    assert s.next_speaker() == "manager"
    s.append_turn("manager", "## Recommendation\nBUY\n")
    assert s.next_speaker() == "trader"
    s.append_turn("trader", "FINAL TRANSACTION PROPOSAL: **BUY**")
    assert s.next_speaker() == "risk_aggressive"
    s.append_turn("risk_aggressive", "Risk Analyst (Aggressive): Risk vote: APPROVE")
    assert s.next_speaker() == "risk_conservative"
    s.append_turn("risk_conservative", "Risk Analyst (Conservative): Risk vote: CUT")
    assert s.next_speaker() == "risk_neutral"
    s.append_turn("risk_neutral", "Risk Analyst (Neutral): Risk vote: CUT")
    assert s.next_speaker() == "portfolio"
    s.append_turn("portfolio", "FINAL TRANSACTION PROPOSAL: **BUY**")
    assert s.next_speaker() is None
    assert s.status == "portfolio"
    hist = s.history_text()
    assert "Risk Analyst (Aggressive)" in hist and "Portfolio Manager" in hist


if __name__ == "__main__":
    test_round_robin_and_complete()
    test_save_load_roundtrip()
    test_extract_prefix()
    test_risk_panel_routing()
    print("All debate session tests passed.")
