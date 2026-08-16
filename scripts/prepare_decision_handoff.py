#!/usr/bin/env python3
"""
Build a frozen facts handoff JSON for Grok Build multi-agent decisions.

Usage:
  python scripts/prepare_decision_handoff.py TSLA --profile Balanced --output decisions/handoff_TSLA.json

Does not call Grok. Run pipeline only, then use /decide-stock or Grok agents with this file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from fetch_data import fetch_stock_data  # noqa: E402
from score import calculate_pillars  # noqa: E402
from montecarlo import run_monte_carlo  # noqa: E402
from dcf import calculate_dcf  # noqa: E402
from report import generate_json_report  # noqa: E402
from agents.decision_schema import build_handoff_bundle  # noqa: E402
from agents.quantitative_analyst.quantitative_analyst import create_quantitative_analyst  # noqa: E402
from backtest.policy import default_policy  # noqa: E402
from backtest.memory import load_prior_journal, DecisionMemory  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Prepare Grok decision handoff (pipeline only)")
    p.add_argument("ticker")
    p.add_argument("--profile", default="Balanced", choices=["Balanced", "Growth", "Value", "Momentum"])
    p.add_argument("--output", default=None, help="Output JSON path")
    p.add_argument("--fast", action="store_true", help="Skip GPU signals (FinBERT); forecasts stay off")
    p.add_argument(
        "--forecasts",
        action="store_true",
        help="Opt-in multi-horizon neural forecasts (default OFF — research-only after audit)",
    )
    p.add_argument("--no-forecasts", action="store_true", help="Force-disable forecasts (default is already off)")
    p.add_argument(
        "--multi-horizon-entry",
        action="store_true",
        help="Opt-in Path C multi-horizon leverage in policy (default OFF)",
    )
    p.add_argument("--debate", action="store_true",
                   help="Include quant debate template text (local facts only; rephrase in Grok Build)")
    p.add_argument("--grok-debate", action="store_true",
                   help="DEPRECATED: external XAI_API_KEY path. Prefer Grok Build /decide-stock (subscription).")
    args = p.parse_args()

    ticker = args.ticker.upper()
    out_dir = REPO / "decisions"
    out_dir.mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else out_dir / f"handoff_{ticker}.json"

    use_forecasts = bool(args.forecasts) and not args.no_forecasts and not args.fast
    print(f"Preparing handoff for {ticker} (profile={args.profile})...")
    print("Decision backend: Grok Build subscription (no API key). This script only freezes pipeline facts.")
    print(f"Forecasts: {use_forecasts} (opt-in) | multi-horizon entry Path C: {args.multi_horizon_entry}")

    data = fetch_stock_data(ticker)
    data["dcf"] = calculate_dcf(data)
    scores = calculate_pillars(
        data,
        args.profile,
        use_gpu_signals=not args.fast,
        use_forecasts=use_forecasts,
    )
    vol = data.get("annual_vol", data["info"].get("beta", 1.0) * 25)
    mc = run_monte_carlo(data["current_price"], vol, scores["overall"], days=252)

    # Primary path: no external LLM. Debate phrasing happens in Grok Build.
    llm = None
    if args.grok_debate:
        print(
            "Note: --grok-debate uses XAI_API_KEY (separate from Grok Build). "
            "For your subscription, omit this flag and run /decide-stock in Grok Build."
        )
        try:
            from agents.llm.grok_client import get_grok_llm
            llm = get_grok_llm(require_key=True)
            print(f"External Grok API model: {llm.model}")
        except Exception as e:
            print(f"Warning: external Grok API unavailable ({e}); template debate only")

    quant_node = create_quantitative_analyst(llm=llm, debate_mode=args.debate or bool(llm) or True)
    quant = quant_node({
        "ticker": ticker,
        "company_of_interest": ticker,
        "messages": [],
        "use_forecasts": use_forecasts,
    })

    # Load episodic memory from journal (if any)
    asof_today = datetime.now().strftime("%Y-%m-%d")
    prior_trades = load_prior_journal(str(REPO), ticker, asof_today)
    memory = DecisionMemory(ticker=ticker)
    for t in prior_trades:
        memory.record_trade(t)
    
    # Snapshot memory as of today (current_price from fetched data)
    current_price = float(data.get("current_price") or 0)
    memory_snap = memory.snapshot_asof(
        asof_today,
        position=0.0,  # no open position in handoff (execution state)
        current_price=current_price,
    )
    memory_text = memory.summary_text(memory_snap)
    memory_dict = memory.apply_to_policy_inputs(memory_snap)
    
    # If no journal runs found, emit explicit "no episodic memory" ledger
    if not prior_trades and not memory.decisions:
        memory_text = (
            f"[Decision Memory asof {asof_today}] ticker={ticker}\n"
            "No episodic memory on disk (journal/runs/).\n"
            "Active flags: none\n"
            "Risk multiplier from memory: 1.0\n"
            "Source: none (clean state)"
        )
        memory_dict = {
            "risk_multiplier": 1.0,
            "block_new_long": False,
            "flags": [],
            "loss_streak": 0,
            "stop_cooldown_active": False,
            "summary": memory_text,
        }

    # Policy hint (with memory if available)
    sig = default_policy(
        {**scores, "ticker": ticker},
        quant_output=quant,
        current_price=current_price,
        atr_pct=float((scores.get("signals") or {}).get("atr_vol", {}).get("atr_percent") or 0),
        mc_risk=(scores.get("signals") or {}).get("mc_risk"),
        profile=args.profile,
        allow_multi_horizon_entry=bool(args.multi_horizon_entry),
        memory=memory_dict,  # inject memory into policy
    )
    policy_hint = {
        "action": sig.action,
        "conviction": sig.conviction,
        "suggested_risk_pct": sig.suggested_risk_pct,
        "stop_price": sig.stop_price,
        "rationale": sig.rationale,
    }

    from recommendation import dual_recommendation
    dual = dual_recommendation(
        scores.get("overall") or 50,
        policy_action=sig.action,
        policy_conviction=sig.conviction,
        policy_rationale=sig.rationale,
        suggested_risk_pct=sig.suggested_risk_pct,
    )
    # JSON after policy so dual research/execute labels are frozen in signals_*.json
    signals_path = generate_json_report(data, scores, mc, args.profile, policy_hint=policy_hint)

    signals_obj = {}
    try:
        with open(signals_path) as f:
            signals_obj = json.load(f)
    except Exception:
        signals_obj = {"overall_score": scores.get("overall"), "pillars": {
            k: scores.get(k) for k in ("fundamentals", "technicals", "valuation", "sentiment", "esg_quality", "risk")
        }}

    quant_slim = {
        "quantitative_conviction": quant.get("quantitative_conviction"),
        "quantitative_signals": quant.get("quantitative_signals"),
        "quantitative_debate_commentary": quant.get("quantitative_debate_commentary"),
        "quantitative_warnings": quant.get("quantitative_warnings"),
        "quantitative_report": (quant.get("quantitative_report") or "")[:6000],
    }

    bundle = build_handoff_bundle(
        ticker=ticker,
        signals_path=str(signals_path),
        signals=signals_obj,
        quant=quant_slim,
        memory_text=memory_text,
        policy_hint=policy_hint,
    )
    bundle["profile"] = args.profile
    bundle["current_price"] = data.get("current_price")
    bundle["last_print"] = data.get("current_price")  # last Close from fetch (live)
    bundle["last_print_source"] = "fetch_stock_data"
    bundle["last_print_date"] = asof_today
    bundle["prepared_at"] = datetime.now(timezone.utc).isoformat()
    bundle["agent_backend"] = "grok-build"
    bundle["measurement_backend"] = "scripts/pipeline"
    bundle["forecasts_enabled"] = use_forecasts
    bundle["multi_horizon_entry_enabled"] = bool(args.multi_horizon_entry)
    bundle["dual_recommendation"] = dual
    bundle["backend_note"] = (
        "Numbers from local Python pipeline. "
        "Research labels (score BUY/etc.) are not trade tickets — follow policy_hint / dual_recommendation.Execute. "
        "Do not invent prices, scores, VaR, or fundamentals."
    )

    with open(out_path, "w") as f:
        json.dump(bundle, f, indent=2, default=str)

    print(f"Handoff written: {out_path}")
    print(
        f"Overall score: {scores.get('overall')} | "
        f"{dual.get('recommendation')} | Policy: {sig.action} ({sig.conviction})"
    )
    if dual.get("policy_conflict"):
        print("⚠️  policy_conflict: Research constructive but Execute FLAT — agents must not force long.")
    print(f"Next (Grok Build subscription): /decide-stock {ticker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
