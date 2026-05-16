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
            )
            signals_available = True
        except Exception as e:
            signals_available = False
            import_error = str(e)

        if signals_available:
            try:
                horizon_data = get_multi_horizon_forecasts(ticker)
                risk_data = get_monte_carlo_risk(ticker)

                # Build multi-horizon table
                multi_horizon_text = ""
                horizons = horizon_data.get("horizons", {})
                for h in ["5d", "10d", "15d", "20d"]:
                    if h in horizons:
                        d = horizons[h]
                        multi_horizon_text += f"| {h} | {d.get('predicted_return', 'N/A')} | {d.get('direction', 'N/A')} |\n"

                quantitative_report = f"""## Quantitative Analysis Report — {ticker}

**Executive Summary**  
Model-driven analysis using LSTM + Chronos-2 with Monte Carlo risk simulation.

**Multi-Horizon Forecasts**
| Horizon | Predicted Return | Direction |
|---------|------------------|-----------|
{multi_horizon_text if multi_horizon_text else "| — | — | — |"}

**Risk Metrics (Monte Carlo)**
- VaR (95%): {risk_data.get('var_95', 'N/A')}%
- CVaR (95%): {risk_data.get('cvar_95', 'N/A')}%
- Simulated Annual Volatility: {risk_data.get('simulated_annual_vol', 'N/A')}%

**Model Consensus**  
Ensemble view from multiple forecasting models.

**Final View**  
Quantitative models provide data-driven input for debate.
"""
            except Exception as e:
                quantitative_report = f"""## Quantitative Analysis Report — {ticker}

**Error computing signals**  
{str(e)[:300]}
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