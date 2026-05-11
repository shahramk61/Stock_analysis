# Multi-Horizon LSTM & Chronos - FINAL CONSISTENT VERSION

                # LSTM: use the SAME logic as the report (small realistic steps from model)
                lstm = None
                try:
                    from signals import get_lstm_forecast
                    horizon_days = int(sel_h.replace('d',''))
                    lstm = get_lstm_forecast(ticker, prediction_length=horizon_days)
                except:
                    lstm = sig.get('lstm_forecast', sig.get('lstm', {}))

                if lstm and "all_predictions" in lstm:
                    inc = lstm["all_predictions"]
                    # If too aggressive, fall back to small steps
                    if max([abs(x) for x in inc]) > 5:
                        total = lstm.get("predicted_return_pct", 0) / 100.0
                        inc = [total / horizon_days * (0.7 + 0.6 * (i / horizon_days)) for i in range(horizon_days)]
                    cum = np.cumsum(inc).tolist()
                    y = ([0.0] + cum) if not use_price else ([last_px] + [last_px * (1 + r / 100) for r in cum])
                    fig_daily.add_trace(go.Scatter(
                        x=x_vals[:len(y)], y=y,
                        mode="lines", name="LSTM",
                        line=dict(color="#22c55e", width=2, dash="dash"),
                        opacity=0.9
                    ))

                # Chronos-2: small linear steps (consistent with report)
                chronos = None
                try:
                    from signals import get_chronos_forecast
                    horizon_days = int(sel_h.replace('d',''))
                    chronos = get_chronos_forecast(ticker, prediction_length=horizon_days)
                except:
                    chronos = sig.get('chronos_forecast', sig.get('chronos', {}))

                if chronos and "predicted_return_pct" in chronos:
                    plen = chronos.get("prediction_length", horizon_days)
                    final = chronos["predicted_return_pct"]
                    daily_inc = [final / plen] * plen
                    cum = np.cumsum(daily_inc).tolist()
                    y = ([0.0] + cum) if not use_price else ([last_px] + [last_px * (1 + r / 100) for r in cum])
                    fig_daily.add_trace(go.Scatter(
                        x=x_vals[:len(y)], y=y,
                        mode="lines", name="Chronos-2",
                        line=dict(color="#f97316", width=2, dash="dot"),
                        opacity=0.9
                    ))