"""
Quantitative Analyst Agent for TradingAgents

This agent provides advanced quantitative signals using our local models
(LSTM, Chronos-2, Monte Carlo risk, multi-horizon forecasts, etc.).
"""

from typing import Dict, Any


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

                # Build multi-horizon table
                multi_horizon_text = ""
                horizons = horizon_data.get("horizons", {})
                for h in ["5d", "10d", "15d", "20d"]:
                    if h in horizons:
                        d = horizons[h]
                        ret = d.get("predicted_return_pct", d.get("predicted_return", "N/A"))
                        direction = d.get("direction", "N/A")
                        multi_horizon_text += f"| {h} | {ret} | {direction} |\n"

                if not multi_horizon_text:
                    multi_horizon_text = "| — | — | — |\n"

                # Simple conviction based on risk
                var = risk_data.get("var_95", 0)
                try:
                    var_val = float(var)
                    if var_val < 3:
                        conviction = "High"
                    elif var_val < 6:
                        conviction = "Medium"
                    else:
                        conviction = "Low"
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
- Beta (vs SPY): {beta_data.get('beta', 'N/A')} (Alpha: {beta_data.get('alpha', 'N/A')})
- IV Rank: {iv_data.get('ivr', 'N/A')}% | IV: {iv_data.get('iv', 'N/A')}% | Skew: {iv_data.get('skew', 'N/A')}

**Conviction Level**: {conviction}

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