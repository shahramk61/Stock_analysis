"""
Quantitative Analyst Agent for TradingAgents

This agent provides advanced quantitative signals using our local models
(LSTM, Chronos-2, Monte Carlo risk, multi-horizon forecasts, etc.).
"""

import os
import sys
from typing import Dict, Any

_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


def create_quantitative_analyst(llm=None):
    """
    Creates a Quantitative Analyst agent node.

    This agent specializes in model-driven forecasts and risk metrics.
    It uses our signals package to generate high-quality quantitative insights.
    """

    def quantitative_analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        ticker = state.get("ticker", state.get("company_of_interest", "UNKNOWN"))

        # Import our signals (lazy import)
        try:
            from signals import (
                get_multi_horizon_forecasts,
                get_monte_carlo_risk,
                get_rolling_beta,
                get_iv_rank_and_skew,
                calculate_altman_beneish,
                get_earnings_surprise,
            )
            signals_available = True
        except Exception as e:
            signals_available = False
            import_error = str(e)

        if signals_available:
            try:
                horizon_data = get_multi_horizon_forecasts(ticker)
                risk_data = get_monte_carlo_risk(ticker)
                beta_data = get_rolling_beta(ticker)
                iv_data = get_iv_rank_and_skew(ticker)
                altman_data = calculate_altman_beneish(ticker)
                earnings_data = get_earnings_surprise(ticker)

                # Build multi-horizon table
                multi_horizon_text = ""
                horizons = horizon_data.get("horizons", {})
                for h in ["5d", "10d", "15d", "20d"]:
                    if h in horizons:
                        d = horizons[h]
                        ret = d.get("predicted_return_pct", d.get("predicted_return", "N/A"))
                        if isinstance(ret, (int, float)):
                            ret = f"{ret:+.2f}%"
                        direction = d.get("direction", "N/A")
                        multi_horizon_text += f"| {h} | {ret} | {direction} |\n"

                if not multi_horizon_text:
                    multi_horizon_text = "| — | — | — |\n"

                # Improved multi-factor conviction logic
                var = risk_data.get("var_95", 0)
                z_score = altman_data.get("z_score", 3.0)
                try:
                    var_val = float(var)
                    z_val = float(z_score)

                    risk_score = 0
                    if var_val > 8:
                        risk_score += 2
                    elif var_val > 5:
                        risk_score += 1

                    if z_val < 1.8:
                        risk_score += 2
                    elif z_val < 3.0:
                        risk_score += 1

                    if risk_score >= 3:
                        conviction = "Low"
                    elif risk_score == 2:
                        conviction = "Medium"
                    else:
                        conviction = "High"
                except:
                    conviction = "Medium"

                quantitative_report = f"""## Quantitative Analysis Report — {ticker}

**Executive Summary**  
Quantitative models (LSTM + Chronos-2) show the current outlook with supporting risk metrics from Monte Carlo simulation.

**Multi-Horizon Forecasts**
| Horizon | Predicted Return | Direction |
|---------|------------------|-----------|
{multi_horizon_text}

**Risk Metrics (Monte Carlo)**
- VaR (95%): {risk_data.get('var_95', 'N/A')}%
- CVaR (95%): {risk_data.get('cvar_95', 'N/A')}%
- Simulated Annual Volatility: {risk_data.get('simulated_annual_vol', 'N/A')}%

**Additional Quantitative Signals**
- **Beta (vs SPY)**: {beta_data.get('beta', 'N/A')} (Alpha: {beta_data.get('alpha', 'N/A')}) — Measures market sensitivity.
- **IV Rank**: {iv_data.get('ivr', 'N/A')}% | IV: {iv_data.get('iv', 'N/A')}% | Skew: {iv_data.get('skew', 'N/A')} — Options market implied uncertainty and hedging bias.
- **Altman Z-Score**: {altman_data.get('z_score', 'N/A')} ({altman_data.get('risk_level', 'N/A')}) — Credit risk / financial distress indicator.
- **Earnings Surprise (avg)**: {earnings_data.get('avg_surprise_pct', 'N/A')}% — Historical tendency to beat/miss estimates.

**Conviction Level**: {conviction}

**Key Takeaways**
- Conviction is {conviction.lower()} primarily due to risk metrics and financial health signals.
- The stock shows a mix of quantitative strengths and risks that should be weighed in the debate.

**Model Consensus**  
Ensemble view combining multiple forecasting models with uncertainty awareness.

**Final View**  
Data-driven quantitative perspective ready for debate and decision making.
"""
            except Exception as e:
                quantitative_report = f"""## Quantitative Analysis Report — {ticker}

**Error computing quantitative signals**  
{str(e)[:350]}
"""
        else:
            quantitative_report = f"""## Quantitative Analysis Report — {ticker}

**Signals package unavailable**  
{import_error if 'import_error' in locals() else 'Unknown import error'}
"""

        return {
            "messages": state.get("messages", []) + [{"role": "assistant", "content": quantitative_report}],
            "quantitative_report": quantitative_report,
        }

    return quantitative_analyst_node