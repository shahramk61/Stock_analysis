# Chronos-2 dynamic handling in Multi-Horizon tab (add after LSTM block):

                # Chronos-2: dynamic call with full horizon
                chronos = None
                try:
                    from signals import get_chronos_forecast
                    horizon_days = int(sel_h.replace('d',''))
                    chronos = get_chronos_forecast(ticker, prediction_length=horizon_days)
                except:
                    pass

                if chronos and "predicted_return_pct" in chronos:
                    plen = chronos.get("prediction_length", horizon_days)
                    final_ret = chronos["predicted_return_pct"]
                    if plen > 0 and final_ret is not None:
                        daily_inc = [final_ret / plen] * plen
                        cum_chronos = np.cumsum(daily_inc).tolist()
                        h_len = len(daily) if daily else len(cum_chronos)
                        cum_chronos = cum_chronos[:h_len]
                        y_chronos = ([0.0] + cum_chronos) if not use_price else ([last_px] + [last_px * (1 + r / 100) for r in cum_chronos])
                        fig_daily.add_trace(go.Scatter(
                            x=x_vals[:len(y_chronos)], y=y_chronos,
                            mode="lines", name="Chronos-2",
                            line=dict(color="#f97316", width=2, dash="dot"),
                            opacity=0.85,
                            hovertemplate=("<b>Chronos-2</b><br>%{x}<br>" + ("$%{y:.2f}" if use_price else "%{y:+.3f}%") + "<extra></extra>")
                        ))