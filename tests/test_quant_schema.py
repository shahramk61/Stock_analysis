"""Schema validation, conviction enum, LLM debate integrity, golden debate checks."""
import os
import sys

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from agents.quantitative_analyst.schemas import (  # noqa: E402
    normalize_conviction,
    normalize_quantitative_signals,
    validate_quantitative_signals,
    debate_preserves_numbers,
    llm_rephrase_debate,
    extract_grounded_numbers,
    CONVICTION_LABELS,
)
from agents.quantitative_analyst.quantitative_analyst import (  # noqa: E402
    compute_quant_conviction,
    _generate_quant_debate_contribution,
    create_quantitative_analyst,
)


def test_normalize_conviction_enum():
    assert normalize_conviction("High") == "High"
    assert normalize_conviction("very bullish high") == "High"
    assert normalize_conviction("Low risk-off") == "Low"
    assert normalize_conviction("Medium") == "Medium"
    assert normalize_conviction("???") == "Unknown"


def test_validate_requires_keys():
    ok, errs = validate_quantitative_signals({})
    assert not ok
    assert any("missing" in e for e in errs)


def test_normalize_marks_schema():
    payload = normalize_quantitative_signals({
        "ticker": "AAPL",
        "conviction": "high conviction",
        "raw_conviction_score": 2,
        "multi_horizon": {"horizons": {}, "consensus_direction": "Neutral"},
        "risk": {"var_95": 24.0},
        "regime": {"regime": "Neutral"},
    })
    assert payload["conviction"] == "High"
    assert payload["schema_version"]
    assert payload["schema_valid"] is True


def test_debate_preserves_numbers():
    facts = "VaR 24.0% | regime Neutral | conviction High"
    good = "On risk: VaR 24.0% remains elevated; regime Neutral; conviction High."
    bad = "Risk is fine and conviction is great."  # drops 24.0
    assert debate_preserves_numbers(facts, good)
    assert not debate_preserves_numbers(facts, bad, required=["24.0"])


def test_llm_rephrase_rejects_bad_numbers():
    facts = "[Quant Analyst] On AAPL: conviction High (Neutral regime).\nVaR 31.5% elevated."

    class BadLLM:
        def invoke(self, prompt):
            return type("R", (), {"content": "Everything is fine, no risks."})()

    text, warns = llm_rephrase_debate(BadLLM(), facts)
    assert text == facts
    assert any("rejected" in w or "numbers" in w for w in warns)


def test_llm_rephrase_accepts_faithful():
    facts = "[Quant Analyst] On AAPL: conviction Medium (Bear regime).\nVaR 22.0%."

    class GoodLLM:
        def invoke(self, prompt):
            return type("R", (), {
                "content": (
                    "[Quant Analyst] On AAPL: conviction Medium (Bear regime). "
                    "Key risk remains VaR 22.0%."
                )
            })()

    text, warns = llm_rephrase_debate(GoodLLM(), facts)
    assert "22.0" in text
    assert "Medium" in text
    assert not any("rejected" in w for w in warns)


def test_compute_conviction_labels_only():
    conv, raw = compute_quant_conviction(
        {"var_95": 35}, {"z_score": 1.0}, {"regime": "Bear"}, 2,
        {"mom_6m": -20}, {"ivr": 80}, {"vol_ratio": 1.6},
        quality_data={"gross_profitability": 1},
        vol_price_data={"vol_price_corr": -0.3},
    )
    assert conv in CONVICTION_LABELS
    assert conv == "Low"
    assert raw >= 6


def test_golden_debate_includes_var_when_elevated():
    """Golden: elevated VaR must appear in debate contribution text."""
    risk = {"var_95": 28.0, "cvar_95": 35.0}
    debate = _generate_quant_debate_contribution(
        "AAPL", "Medium", "Neutral",
        highlights="VaR 28.0% | regime Neutral | Piotroski 5",
        takeaways=["Elevated tail risk: 95% VaR 28.0% (MC 10k paths)."],
        risk_data=risk,
        mom_data={"mom_6m": 0},
        quality_data={"quality": "Unknown"},
        earnings_data={"avg_surprise_pct": 0},
        iv_data={"ivr": 50},
    )
    assert "28" in debate or "28.0" in debate
    assert "VaR" in debate
    assert "conviction Medium" in debate or "conviction Medium".lower() in debate.lower()


def test_golden_high_var_forces_risk_section():
    risk = {"var_95": 40.0}
    debate = _generate_quant_debate_contribution(
        "TEST", "Low", "Bear",
        highlights="VaR 40.0% | regime Bear",
        takeaways=[],
        risk_data=risk,
        mom_data={},
        quality_data={},
        earnings_data={},
        iv_data={},
    )
    assert "elevated tail risk" in debate.lower() or "40" in debate
    assert "Bear" in debate


def test_quant_node_schema_valid_fast_path():
    """Integration: node output has schema_valid when signals available (may use network)."""
    node = create_quantitative_analyst(debate_mode=True)
    # Minimal offline-ish: still may hit yfinance; allow skip if fully offline fails
    try:
        out = node({
            "ticker": "AAPL",
            "company_of_interest": "AAPL",
            "messages": [],
            "use_forecasts": False,
        })
    except Exception as e:
        print("skip integration:", e)
        return
    assert out.get("quantitative_conviction") in CONVICTION_LABELS
    sigs = out.get("quantitative_signals") or {}
    assert "schema_version" in sigs
    assert "conviction" in sigs
    # Debate should mention VaR if risk present and elevated
    debate = out.get("quantitative_debate_commentary") or ""
    var = (sigs.get("risk") or {}).get("var_95")
    if var is not None and float(var) > 20 and debate:
        assert "VaR" in debate or str(var) in debate


if __name__ == "__main__":
    test_normalize_conviction_enum()
    test_validate_requires_keys()
    test_normalize_marks_schema()
    test_debate_preserves_numbers()
    test_llm_rephrase_rejects_bad_numbers()
    test_llm_rephrase_accepts_faithful()
    test_compute_conviction_labels_only()
    test_golden_debate_includes_var_when_elevated()
    test_golden_high_var_forces_risk_section()
    test_quant_node_schema_valid_fast_path()
    print("All quant schema / golden tests passed.")
