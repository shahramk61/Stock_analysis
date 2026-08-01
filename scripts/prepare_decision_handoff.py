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


def main():
    p = argparse.ArgumentParser(description="Prepare Grok decision handoff (pipeline only)")
    p.add_argument("ticker")
    p.add_argument("--profile", default="Balanced", choices=["Balanced", "Growth", "Value", "Momentum"])
    p.add_argument("--output", default=None, help="Output JSON path")
    p.add_argument("--fast", action="store_true", help="Skip GPU/forecast signals")
    p.add_argument("--no-forecasts", action="store_true")
    p.add_argument("--debate", action="store_true", help="Include quant debate template")
    p.add_argument("--grok-debate", action="store_true", help="Rephrase debate via Grok API if XAI_API_KEY set")
    args = p.parse_args()

    ticker = args.ticker.upper()
    out_dir = REPO / "decisions"
    out_dir.mkdir(exist_ok=True)
    out_path = Path(args.output) if args.output else out_dir / f"handoff_{ticker}.json"

    print(f"Preparing handoff for {ticker} (profile={args.profile})...")

    data = fetch_stock_data(ticker)
    data["dcf"] = calculate_dcf(data)
    scores = calculate_pillars(
        data,
        args.profile,
        use_gpu_signals=not args.fast,
        use_forecasts=not args.no_forecasts and not args.fast,
    )
    vol = data.get("annual_vol", data["info"].get("beta", 1.0) * 25)
    mc = run_monte_carlo(data["current_price"], vol, scores["overall"], days=252)
    signals_path = generate_json_report(data, scores, mc, args.profile)

    llm = None
    if args.grok_debate:
        try:
            from agents.llm.grok_client import get_grok_llm
            llm = get_grok_llm(require_key=True)
            print(f"Grok LLM: {llm.model}")
        except Exception as e:
            print(f"Warning: Grok LLM unavailable ({e}); template debate only")

    quant_node = create_quantitative_analyst(llm=llm, debate_mode=args.debate or bool(llm))
    quant = quant_node({
        "ticker": ticker,
        "company_of_interest": ticker,
        "messages": [],
        "use_forecasts": not args.no_forecasts and not args.fast,
    })

    # Stateless policy hint (memory can be added later from journal)
    sig = default_policy(
        {**scores, "ticker": ticker},
        quant_output=quant,
        current_price=float(data["current_price"]),
        atr_pct=float((scores.get("signals") or {}).get("atr_vol", {}).get("atr_percent") or 0),
        mc_risk=(scores.get("signals") or {}).get("mc_risk"),
        profile=args.profile,
    )
    policy_hint = {
        "action": sig.action,
        "conviction": sig.conviction,
        "suggested_risk_pct": sig.suggested_risk_pct,
        "stop_price": sig.stop_price,
        "rationale": sig.rationale,
    }

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
        memory_text="",
        policy_hint=policy_hint,
    )
    bundle["profile"] = args.profile
    bundle["current_price"] = data.get("current_price")
    bundle["prepared_at"] = datetime.now(timezone.utc).isoformat()
    bundle["agent_backend"] = "grok-build"
    bundle["measurement_backend"] = "scripts/pipeline"

    with open(out_path, "w") as f:
        json.dump(bundle, f, indent=2, default=str)

    print(f"Handoff written: {out_path}")
    print(f"Overall score: {scores.get('overall')} | Policy hint: {sig.action} ({sig.conviction})")
    print("Next: open Grok Build and run /decide-stock", ticker, "using this handoff.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
