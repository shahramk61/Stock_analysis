"""
Quantitative Analyst Agent for TradingAgents

This agent provides advanced quantitative signals using our local models
(7-model neural ensemble: NHITS/TFT/PatchTST/NBEATS/TCN + LSTM + Chronos-2,
plus HMM regime, GARCH vol, Monte Carlo risk, liquidity/volume alphas, quality,
momentum, and statistical factors).

v1: Rich data provider (quantitative_report + structured signals).
v2 stub: Optional debate_commentary when llm is supplied (template first;
         can be upgraded to light llm synthesis in TradingAgents).
"""

import os
import sys
from typing import Dict, Any

_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


# --- Helpers for robustness and v2 features ---------------------------------

def _safe_fetch(name: str, func, defaults: Dict[str, Any], warnings: list, *args, **kwargs) -> Dict[str, Any]:
    """Fetch a signal safely. Never let one bad signal kill the whole report."""
    try:
        result = func(*args, **kwargs)
        if isinstance(result, dict):
            return result
        warnings.append(f"{name}: non-dict return, using defaults")
        return defaults
    except Exception as e:
        warnings.append(f"{name}: {str(e)[:120]}")
        return defaults


def compute_quant_conviction(
    risk_data: dict,
    altman_data: dict,
    regime_data: dict,
    piotroski: Any,
    mom_data: dict,
    iv_data: dict,
    garch_data: dict,
    quality_data: dict | None = None,
    vol_price_data: dict | None = None,
    **extra,
) -> tuple[str, int]:
    """
    Tunable multi-factor conviction engine for the Quantitative Analyst.

    Returns (conviction_label, raw_risk_score).

    Tuning guidance (edit thresholds / points here):
      - Tail risk (VaR) and financial distress (Z) are high-impact.
      - Regime, quality (Piotroski + GP/accruals), momentum, and implied vol are medium.
      - Add new signals by extending the point logic below and passing them in.
    """
    try:
        var_val = float(risk_data.get("var_95", 20))
        z_val = float(altman_data.get("z_score", 3.0))
        regime = str(regime_data.get("regime", "Neutral"))
        piot = int(piotroski) if isinstance(piotroski, (int, float)) else 5
        mom_6m = float(mom_data.get("mom_6m", 0))
        ivr = float(iv_data.get("ivr", 50))
        garch_ratio = float(garch_data.get("vol_ratio", 1.0))

        # Optional new factors
        gp = (quality_data or {}).get("gross_profitability", 0) or 0
        vol_corr = (vol_price_data or {}).get("vol_price_corr", 0) or 0

        risk_score = 0

        # === Tail / Realized Risk ===
        if var_val > 30:
            risk_score += 3
        elif var_val > 20:
            risk_score += 2
        elif var_val > 10:
            risk_score += 1

        # === Financial Health / Quality ===
        if z_val < 1.8:
            risk_score += 2
        elif z_val < 3.0:
            risk_score += 1

        if piot <= 3:
            risk_score += 1
        elif piot >= 8:
            risk_score -= 1

        if gp > 35:
            risk_score -= 1
        elif gp < 5:
            risk_score += 1

        # === Regime ===
        if regime == "Bear":
            risk_score += 2
        # Neutral adds 0; Bull can be used to slightly reduce elsewhere if desired

        # === Momentum / Trend ===
        if mom_6m < -15:
            risk_score += 1
        elif mom_6m > 25:
            risk_score -= 1

        # === Implied & Forward Vol ===
        if ivr > 70:
            risk_score += 1
        if garch_ratio > 1.45:
            risk_score += 1

        # === Volume / Flow confirmation (new) ===
        if vol_corr < -0.2:
            risk_score += 1  # volume diverging from price = caution

        # Map to label (tune these cutoffs)
        if risk_score >= 6:
            conviction = "Low"
        elif risk_score >= 3:
            conviction = "Medium"
        else:
            conviction = "High"

        return conviction, risk_score
    except Exception:
        return "Medium", 3


def _generate_debate_stub(ticker: str, conviction: str, regime: str, highlights: str) -> str:
    """
    v2 debate participation stub.

    Returns a concise, speakable contribution the Quant Analyst could offer
    in the Researcher bull/bear debate.

    This is deliberately template-driven and LLM-free so the smoke test and
    local usage never require API keys. In a full TradingAgents environment
    where `llm` is a real model, you can replace/augment the body with:

        prompt = f"Using ONLY these quantitative facts, write a 2-3 sentence ...: {highlights}"
        debate_commentary = llm.invoke(prompt)   # or equivalent

    Keep the signals as the source of truth; use LLM only for phrasing.
    """
    tone = {
        "High": "leans constructive for the bull case but still flags risk limits",
        "Low": "provides concrete reasons the bear case should emphasize",
        "Medium": "is balanced — useful neutral data for both sides",
    }.get(conviction, "is mixed")

    return (
        f"[Quant Analyst] On {ticker}: conviction {conviction} ({regime} regime). "
        f"{highlights}. This data {tone}."
    )


def create_quantitative_analyst(llm=None, debate_mode: bool = False):
    """
    Creates a Quantitative Analyst agent node.

    This agent specializes in model-driven forecasts and risk metrics.
    It uses our signals package (stock_signals.py) to generate high-quality
    quantitative insights. Primarily a rich data provider for Researchers/Trader.
    """

    def quantitative_analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        ticker = state.get("ticker", state.get("company_of_interest", "UNKNOWN"))
        warnings: list[str] = []

        # --- Lazy import of canonical signals (never hard-fail the node) ---
        try:
            from signals import (
                get_multi_horizon_forecasts,
                get_monte_carlo_risk,
                get_rolling_beta,
                get_iv_rank_and_skew,
                calculate_altman_beneish,
                get_earnings_surprise,
                get_market_regime,
                get_garch_forecast,
                calculate_piotroski_f_score,
                get_atr_volatility_clustering,
                get_momentum_and_52w_high,
                get_relative_strength,
                get_amihud_illiquidity,
                get_obv,
                get_chaikin_money_flow,
                # Additional signals for richer reports (v2 polish)
                get_quality_accruals_gross_profit,
                get_volume_price_correlation,
                get_simple_formulaic_alpha,
                get_share_turnover,
            )
            signals_available = True
        except Exception as e:
            signals_available = False
            import_error = str(e)

        if not signals_available:
            quantitative_report = f"""## Quantitative Analysis Report — {ticker}

**Signals package unavailable**  
{import_error if 'import_error' in locals() else 'Unknown import error'}
"""
            return {
                "messages": state.get("messages", []) + [{"role": "assistant", "content": quantitative_report}],
                "quantitative_report": quantitative_report,
                "quantitative_conviction": "Unknown",
                "quantitative_warnings": [import_error if 'import_error' in locals() else "import failed"],
                "quantitative_signals": {},
                "quantitative_debate_commentary": "",
            }

        # --- Safe per-signal fetching (one failure does not poison everything) ---
        defaults = {
            "horizons": {},
            "var_95": 20.0, "cvar_95": 28.0, "simulated_annual_vol": 30.0,
            "z_score": 3.0, "risk_level": "Medium",
            "regime": "Neutral", "probs": [0.33, 0.34, 0.33],
            "ivr": 50, "iv": 30.0, "skew": 0.0,
            "mom_6m": 0.0, "mom_12m": 0.0, "pct_from_52w_high": 0.0,
        }

        horizon_data   = _safe_fetch("multi_horizon", get_multi_horizon_forecasts, {"horizons": {}}, warnings, ticker)
        risk_data      = _safe_fetch("monte_carlo_risk", get_monte_carlo_risk, {"var_95": 20.0, "cvar_95": 28.0, "simulated_annual_vol": 30.0}, warnings, ticker)
        beta_data      = _safe_fetch("rolling_beta", get_rolling_beta, {"beta": 1.0, "alpha": 0.0}, warnings, ticker)
        iv_data        = _safe_fetch("iv_rank_skew", get_iv_rank_and_skew, {"ivr": 50, "iv": 30.0, "skew": 0.0}, warnings, ticker)
        altman_data    = _safe_fetch("altman_beneish", calculate_altman_beneish, {"z_score": 3.0, "risk_level": "Medium"}, warnings, ticker)
        earnings_data  = _safe_fetch("earnings_surprise", get_earnings_surprise, {"avg_surprise_pct": 0.0}, warnings, ticker)

        regime_data    = _safe_fetch("market_regime", get_market_regime, {"regime": "Neutral", "probs": [0.33, 0.34, 0.33]}, warnings, ticker)
        garch_data     = _safe_fetch("garch", get_garch_forecast, {"garch_vol_forecast": 0.0, "vol_ratio": 1.0}, warnings, ticker)
        # Piotroski returns a scalar (0-9), not a dict — handle specially
        try:
            piotroski = calculate_piotroski_f_score(ticker)
            if not isinstance(piotroski, (int, float)):
                piotroski = 5
        except Exception as e:
            warnings.append(f"piotroski: {str(e)[:100]}")
            piotroski = 5
        atr_data       = _safe_fetch("atr_vol", get_atr_volatility_clustering, {"atr_percent": 0.0, "vol_clustering": "Normal", "risk_level": "Normal"}, warnings, ticker)
        mom_data       = _safe_fetch("momentum_52w", get_momentum_and_52w_high, {"mom_6m": 0.0, "mom_12m": 0.0, "pct_from_52w_high": 0.0}, warnings, ticker)
        rs_data        = _safe_fetch("rel_strength", get_relative_strength, {"rs_spy": 0.0, "rs_sector": 0.0}, warnings, ticker)
        amihud         = _safe_fetch("amihud", get_amihud_illiquidity, {"amihud": 0.0}, warnings, ticker)
        obv_data       = _safe_fetch("obv", get_obv, {"obv_change_20d_pct": 0.0}, warnings, ticker)
        cmf_data       = _safe_fetch("cmf", get_chaikin_money_flow, {"cmf": 0.0, "cmf_signal": "Neutral"}, warnings, ticker)

        # New signals (polish)
        quality_data   = _safe_fetch("quality_gp_accruals", get_quality_accruals_gross_profit, {"gross_profitability": 0.0, "accruals_ratio": 0.0, "quality": "Unknown"}, warnings, ticker)
        vol_price_data = _safe_fetch("vol_price_corr", get_volume_price_correlation, {"vol_price_corr": 0.0, "interpretation": "Neutral"}, warnings, ticker)
        formulaic_data = _safe_fetch("formulaic_alpha", get_simple_formulaic_alpha, {"alpha": 0.0, "alpha_signal": "Neutral"}, warnings, ticker)
        turnover_data  = _safe_fetch("share_turnover", get_share_turnover, {"turnover": 0.0}, warnings, ticker)

        # --- Richer ensemble metadata from horizon_data ---
        horizons = horizon_data.get("horizons", {})
        multi_horizon_text = ""
        for h in ["5d", "10d", "15d", "20d"]:
            if h in horizons:
                d = horizons[h]
                ret = d.get("predicted_return_pct", d.get("median_return_pct", d.get("predicted_return", "N/A")))
                if isinstance(ret, (int, float)):
                    ret = f"{ret:+.2f}%"
                direction = d.get("direction", "N/A")
                multi_horizon_text += f"| {h} | {ret} | {direction} |\n"
        if not multi_horizon_text:
            multi_horizon_text = "| — | — | — |\n"

        consensus   = horizon_data.get("consensus_direction", "Neutral")
        trend       = horizon_data.get("trend_signal", "Stable")
        disagreement = horizon_data.get("model_disagreement", horizon_data.get("horizons", {}).get("5d", {}).get("model_disagreement", "N/A"))
        num_models  = horizon_data.get("horizons", {}).get("5d", {}).get("num_models", "N/A")

        # --- Conviction (now using the clean tunable helper) ---
        conviction, raw_score = compute_quant_conviction(
            risk_data, altman_data, regime_data, piotroski, mom_data, iv_data, garch_data,
            quality_data=quality_data,
            vol_price_data=vol_price_data,
        )

        # --- Data-driven Key Takeaways (extended) ---
        takeaways = []
        if regime_data.get("regime") == "Bear":
            takeaways.append("HMM regime currently Bear — downside momentum in recent returns.")
        elif regime_data.get("regime") == "Bull":
            takeaways.append("HMM regime Bull — positive return regime detected.")
        if float(risk_data.get("var_95", 0)) > 20:
            takeaways.append(f"Elevated tail risk: 95% VaR {risk_data.get('var_95')}% (MC 10k paths).")
        if altman_data.get("risk_level") == "Distress" or float(altman_data.get("z_score", 3)) < 1.8:
            takeaways.append("Altman Z-Score signals financial distress risk.")
        elif altman_data.get("risk_level") == "Grey":
            takeaways.append("Altman Z-Score in Grey zone — monitor credit/financial health.")
        if isinstance(piotroski, (int, float)) and piotroski >= 7:
            takeaways.append(f"Strong financial health: Piotroski F-Score {piotroski}/9.")
        elif isinstance(piotroski, (int, float)) and piotroski <= 3:
            takeaways.append(f"Weak fundamentals per Piotroski F-Score ({piotroski}/9).")
        if quality_data.get("quality") == "High":
            takeaways.append(f"High quality (gross profitability {quality_data.get('gross_profitability')}% + low accruals).")
        mom_6 = mom_data.get("mom_6m", 0)
        if isinstance(mom_6, (int, float)) and abs(mom_6) > 10:
            sign = "strong positive" if mom_6 > 0 else "weak"
            takeaways.append(f"6-month momentum {mom_6:+.1f}% ({sign}).")
        if iv_data.get("ivr", 0) > 65:
            takeaways.append(f"Options market showing elevated uncertainty (IV Rank {iv_data.get('ivr')}% ).")
        if atr_data.get("vol_clustering") == "High":
            takeaways.append("ATR/volatility clustering elevated vs 1y average.")
        if vol_price_data.get("vol_price_corr", 0) < -0.15:
            takeaways.append("Volume-price correlation negative — price moves lack volume confirmation.")
        if not takeaways:
            takeaways.append("Quantitative signals mixed; no dominant extreme factors.")

        takeaways_bullets = "\n".join(f"- {t}" for t in takeaways[:5])

        # --- Convenience values for template & debate stub ---
        regime_str = regime_data.get("regime", "Neutral")
        garch_f = garch_data.get("garch_vol_forecast", "N/A")
        cmf_sig = cmf_data.get("cmf_signal", "Neutral")
        obv_ch = obv_data.get("obv_change_20d_pct", 0)

        # --- Build the main report (data-provider focused) ---
        quantitative_report = f"""## Quantitative Analysis Report — {ticker}

**Executive Summary**  
7-model neural ensemble (NHITS + TFT + PatchTST + NBEATS + TCN + LSTM + Chronos-2) + HMM/GARCH/statistical factors for {ticker}. Multi-horizon outlook, tail-risk (Monte Carlo), regime, quality, momentum, liquidity/volume alphas, and formulaic signals.

**Multi-Horizon Ensemble Forecasts** (consensus: {consensus}, trend: {trend}, models: {num_models}, disagreement: {disagreement})
| Horizon | Predicted Return | Direction |
|---------|------------------|-----------|
{multi_horizon_text}

**Risk & Volatility**
- Monte Carlo (10k paths): VaR 95% {risk_data.get('var_95', 'N/A')}% | CVaR 95% {risk_data.get('cvar_95', 'N/A')}% | Sim. Ann. Vol {risk_data.get('simulated_annual_vol', 'N/A')}%
- GARCH(1,1) 5d vol forecast: {garch_f}% (ratio vs hist: {garch_data.get('vol_ratio', 'N/A')})
- ATR% / Vol clustering: {atr_data.get('atr_percent', 'N/A')}% | {atr_data.get('vol_clustering', 'N/A')} ({atr_data.get('risk_level', 'N/A')})

**Market Regime (HMM)**
- Current: **{regime_str}** (probs: {regime_data.get('probs', [])})

**Quality, Momentum & Relative Strength**
- Piotroski F-Score: {piotroski}/9 | Quality (GP/Accruals): {quality_data.get('quality', 'Unknown')} (GP {quality_data.get('gross_profitability', 'N/A')}%, accruals {quality_data.get('accruals_ratio', 'N/A')})
- Altman Z-Score: {altman_data.get('z_score', 'N/A')} ({altman_data.get('risk_level', 'N/A')})
- Momentum: 6m {mom_data.get('mom_6m', 'N/A')}% | 12m {mom_data.get('mom_12m', 'N/A')}% | 52w high proximity: {mom_data.get('pct_from_52w_high', 'N/A')}%
- Rel. Strength: vs SPY {rs_data.get('rs_spy', 'N/A')}% | vs Sector {rs_data.get('rs_sector', 'N/A')}%

**Liquidity, Flow, Volume & Options**
- IV Rank: {iv_data.get('ivr', 'N/A')}% | IV: {iv_data.get('iv', 'N/A')}% | Skew: {iv_data.get('skew', 'N/A')}
- OBV 20d Δ: {obv_ch}% | CMF: {cmf_data.get('cmf', 'N/A')} ({cmf_sig})
- Vol-Price Corr: {vol_price_data.get('vol_price_corr', 'N/A')} ({vol_price_data.get('interpretation', 'N/A')})
- Formulaic Alpha (intraday mom): {formulaic_data.get('alpha', 'N/A')} ({formulaic_data.get('alpha_signal', 'N/A')})
- Share Turnover (ann.): {turnover_data.get('turnover', 'N/A')}%
- Amihud Illiquidity: {amihud.get('amihud', 'N/A')}
- Beta (vs SPY): {beta_data.get('beta', 'N/A')} (α: {beta_data.get('alpha', 'N/A')})
- Earnings surprise (avg 8q): {earnings_data.get('avg_surprise_pct', 'N/A')}%

**Conviction Level**: {conviction} (raw score: {raw_score})

**Key Takeaways**
{takeaways_bullets}

**Model Consensus**  
Neural ensemble median + statistical overlays (HMM regime, GARCH forward vol, liquidity/quality/volume factors). Uncertainty via MC tails + model disagreement.

**Final View**  
Rich quantitative data layer ready for Researcher debate, risk sizing, and Trader decisioning.
"""

        # --- v2 Debate participation stub (template-driven; LLM-upgradeable) ---
        debate_commentary = ""
        use_debate = debate_mode or (llm is not None)
        if use_debate:
            hl = (
                f"VaR {risk_data.get('var_95')}% | regime {regime_str} | "
                f"Piotroski {piotroski} | Mom6m {mom_data.get('mom_6m')}% | IVR {iv_data.get('ivr')}%"
            )
            debate_commentary = _generate_debate_stub(ticker, conviction, regime_str, hl)

        # --- Structured output for downstream agents (highly valuable in TradingAgents) ---
        quantitative_signals = {
            "ticker": ticker,
            "conviction": conviction,
            "raw_conviction_score": raw_score,
            "multi_horizon": {
                "horizons": horizons,
                "consensus_direction": consensus,
                "trend_signal": trend,
                "model_disagreement": disagreement,
            },
            "risk": risk_data,
            "regime": regime_data,
            "quality": quality_data,
            "momentum": mom_data,
            "liquidity_flow": {
                "iv": iv_data,
                "obv_20d_pct": obv_ch,
                "cmf": cmf_data.get("cmf"),
                "cmf_signal": cmf_sig,
                "vol_price_corr": vol_price_data.get("vol_price_corr"),
                "amihud": amihud.get("amihud"),
                "turnover": turnover_data.get("turnover"),
            },
            "beta": beta_data,
            "earnings_surprise": earnings_data.get("avg_surprise_pct"),
            "garch": garch_data,
            "atr": atr_data,
        }

        return {
            "messages": state.get("messages", []) + [{"role": "assistant", "content": quantitative_report}],
            "quantitative_report": quantitative_report,
            "quantitative_conviction": conviction,
            "quantitative_signals": quantitative_signals,
            "quantitative_warnings": warnings,
            "quantitative_debate_commentary": debate_commentary,
        }

    return quantitative_analyst_node