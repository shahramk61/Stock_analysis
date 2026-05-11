import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '.claude', 'skills', 'stock-analysis', 'scripts'))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd

# ... (keep all existing imports and helper functions)

# In the Multi-Horizon tab (around line 380-420), replace the LSTM block with this dynamic version:

                # LSTM: dynamic call with full horizon
                lstm = None
                try:
                    from signals import get_lstm_forecast
                    horizon_days = int(sel_h.replace('d',''))
                    lstm = get_lstm_forecast(ticker, prediction_length=horizon_days)
                except Exception as e:
                    st.warning(f"Could not load dynamic LSTM for {sel_h}: {e}")

                if lstm and "all_predictions" in lstm:
                    inc_returns = lstm["all_predictions"]
                    if len(inc_returns) < horizon_days:
                        # Extend with last daily step if model returned fewer
                        last_step = inc_returns[-1] if inc_returns else 0.0
                        inc_returns = inc_returns + [last_step] * (horizon_days - len(inc_returns))
                    cum_lstm = np.cumsum(inc_returns).tolist()
                    h_len = len(daily) if daily else len(cum_lstm)
                    cum_lstm = cum_lstm[:h_len]
                    y_lstm = ([0.0] + cum_lstm) if not use_price else ([last_px] + [last_px * (1 + r / 100) for r in cum_lstm])
                    fig_daily.add_trace(go.Scatter(
                        x=x_vals[:len(y_lstm)], y=y_lstm,
                        mode="lines", name="LSTM",
                        line=dict(color="#22c55e", width=2, dash="dash"),
                        opacity=0.85,
                        hovertemplate=("<b>LSTM</b><br>%{x}<br>" + ("$%{y:.2f}" if use_price else "%{y:+.3f}%") + "<extra></extra>")
                    ))

# Also update the GPU/DL tab to show the dynamic length
# ... rest of file unchanged