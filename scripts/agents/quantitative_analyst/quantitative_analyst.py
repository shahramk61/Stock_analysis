"""
Quantitative Analyst Agent for TradingAgents

This agent provides advanced quantitative signals using our local models
(LSTM, Chronos-2, Monte Carlo risk, etc.).
"""

from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def create_quantitative_analyst(llm):
    """
    Creates a Quantitative Analyst agent node.
    
    This agent specializes in model-driven forecasts and risk metrics.
    It uses our signals package to generate high-quality quantitative insights.
    """

    def quantitative_analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main node function for the Quantitative Analyst.
        """
        # TODO: Extract ticker and other context from state
        ticker = state.get("ticker", "UNKNOWN")

        # TODO: Call our signals package here
        # from signals import get_multi_horizon_forecasts, get_monte_carlo_risk
        # forecasts = get_multi_horizon_forecasts(ticker)
        # risk = get_monte_carlo_risk(ticker)

        # Placeholder for now
        quantitative_report = f"""
## Quantitative Analysis Report — {ticker}

**Executive Summary**  
[Model-driven summary will appear here]

**Multi-Horizon Forecasts**
| Horizon | Predicted Return | Direction | Confidence |
|---------|------------------|-----------|------------|
| 5d      | —                | —         | —          |
| 10d     | —                | —         | —          |
| 20d     | —                | —         | —          |

**Risk Metrics (Monte Carlo)**
- VaR (95%): —
- CVaR (95%): —
- Simulated Volatility: —

**Model Consensus**  
[To be implemented]

**Final View**  
[Quantitative conviction level + reasoning]
"""

        return {
            "messages": state.get("messages", []) + [quantitative_report],
            "quantitative_report": quantitative_report,
        }

    return quantitative_analyst_node