"""Structural checks: agent prompts encode dual labels and named placeholders."""
from __future__ import annotations

import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def test_prompts_md_has_dual_and_integrity():
    text = _read("scripts/agents/PROMPTS.md")
    assert "dual_recommendation" in text
    assert "policy_hint" in text
    assert "Research BUY" in text or "Research" in text
    assert "cross-ticker" in text.lower() or "cross-ticker" in text
    assert "{quantitative_signals_json}" in text
    assert "schema_version" in text
    assert "early_stop" in text
    assert "Independent sequential" in text or "independent sequential" in text.lower()


def test_grok_agents_have_dual_labels():
    for name in (
        "stock-bull.md",
        "stock-bear.md",
        "stock-research-manager.md",
        "stock-trader.md",
    ):
        text = _read(f".grok/agents/{name}")
        assert "dual_recommendation" in text or "Dual labels" in text or "Dual-label" in text, name
        assert "policy_hint" in text or "policy_hint" in text.replace("`", ""), name
        assert "invent" in text.lower(), name


def test_trader_json_schema_fields_documented():
    text = _read(".grok/agents/stock-trader.md")
    for field in (
        "policy_conflict",
        "policy_action",
        "debate_path",
        "pipeline_refs",
        "schema_version",
        "early_stop",
    ):
        assert field in text, f"missing {field}"


def test_stock_decision_skill_requires_sequential_and_early_stop():
    text = _read(".grok/skills/stock-decision/SKILL.md")
    assert "Independent sequential" in text or "independent sequential" in text.lower()
    assert "early_stop" in text or "Early stop" in text
    assert "dual_recommendation" in text
    assert "policy_conflict" in text
    assert "risk-panel" in text or "risk_panel" in text
    assert "portfolio-manager" in text or "Portfolio Manager" in text


def test_risk_and_portfolio_agents_exist():
    for name in (
        "stock-risk-aggressive.md",
        "stock-risk-conservative.md",
        "stock-risk-neutral.md",
        "stock-portfolio-manager.md",
    ):
        text = _read(f".grok/agents/{name}")
        assert "dual_recommendation" in text or "Dual labels" in text, name
        assert "policy_hint" in text, name
        assert "invent" in text.lower(), name


if __name__ == "__main__":
    test_prompts_md_has_dual_and_integrity()
    test_grok_agents_have_dual_labels()
    test_trader_json_schema_fields_documented()
    test_stock_decision_skill_requires_sequential_and_early_stop()
    test_risk_and_portfolio_agents_exist()
    print("All agent prompt integrity tests passed.")
