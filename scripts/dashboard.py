"""
Stock Analysis Dashboard — v4.10
Streamlit UI for the full signal pipeline (CPU + GPU signals).
Run: streamlit run scripts/dashboard.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '.claude', 'skills', 'stock-analysis', 'scripts'))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd

st.set_page_config(
    page_title="Stock Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.title("📊 Stock Analyzer")
    st.caption("v4.10 · GPU-accelerated · Multi-Horizon Ensemble")
    ticker = st.text_input("Ticker Symbol", value="AAPL", max_chars=8).upper().strip()
    profile = st.selectbox("Investor Profile", ["Balanced", "Growth", "Value", "Momentum"])
    use_gpu = st.toggle("Enable GPU Signals (LSTM + DL Ensemble)", value=True)
    st.caption("⚠️ GPU signals add ~2-3 min per analysis")
    run_btn = st.button("🔍 Run Analysis", type="primary", use_container_width=True)
    st.divider()
    st.markdown("**Compare Tickers**")
    compare_tickers = st.text_input("Tickers (comma-separated)", placeholder="AAPL, MSFT, NVDA")
    compare_btn = st.button("📊 Compare", use_container_width=True)


def score_label(s):
    if s >= 75: return "Strong Buy"
    if s >= 60: return "Buy"
    if s >= 50: return "Hold/Watch"
    if s >= 35: return "Caution"
    return "Avoid"

def score_emoji(s):
    if s >= 75: return "🟢🟢"
    if s >= 60: return "🟢"
    if s >= 50: return "🟡"
    if s >= 35: return "🔴"
    return "🔴🔴"


@st.cache_data(ttl=300, show_spinner=False)
def run_analysis(ticker, profile, use_gpu):
    from fetch_data import fetch_stock_data
    from score import calculate_pillars
    from montecarlo import run_monte_carlo
    from dcf import calculate_dcf
    data = fetch_stock_data(ticker)
    data['dcf'] = calculate_dcf(data)
    if not use_gpu:
        import signals as sm
        sm.get_lstm_forecast     = lambda t, **k: {"direction": "Disabled", "predicted_return_pct": 0, "signal_strength": 0, "device_used": "disabled"}
        sm.get_finbert_sentiment = lambda t, **k: {"overall_sentiment": "Disabled", "sentiment_score": 50, "num_articles": 0}
        sm.get_nhits_tft_patchtst_ensemble       = lambda t, **k: {"direction": "Disabled", "predicted_return_pct": 0, "uncertainty_pct": 0, "models_used": 0, "device_used": "disabled"}
    scores = calculate_pillars(data, profile)
    mc12 = run_monte_carlo(data['current_price'], data.get('annual_vol', 25), scores['overall'], days=252)
    mc36 = run_monte_carlo(data['current_price'], data.get('annual_vol', 25), scores['overall'], days=756)
    return data, scores, mc12, mc36


def pillar_radar(scores):
    cats = ['Fundamentals','Technicals','Valuation','Sentiment','ESG/Quality']
    vals = [scores['fundamentals'], scores['technicals'], scores['valuation'], scores['sentiment'], scores['esg_quality']]
    fig = go.Figure(go.Scatterpolar(r=vals+[vals[0]], theta=cats+[cats[0]],
        fill='toself', line_color='#3b82f6', fillcolor='rgba(59,130,246,0.2)'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,100])),
        template="plotly_dark", height=300, margin=dict(t=20,b=20,l=40,r=40), showlegend=False)
    return fig


def mc_chart(price, mc12, mc36, ticker):
    labels = ["p10\n12mo","Median\n12mo","p90\n12mo","p10\n36mo","Median\n36mo","p90\n36mo"]
    vals   = [mc12['p10'], mc12['median'], mc12['p90'], mc36['p10'], mc36['median'], mc36['p90']]
    colors = ['#ef4444','#3b82f6','#22c55e','#f97316','#6366f1','#10b981']
    fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=colors,
        text=[f"${v:.0f}\n{(v/price-1)*100:+.0f}%" for v in vals], textposition='outside'))
    fig.add_hline(y=price, line_dash="dash", line_color="white",
        annotation_text=f"Current ${price:.2f}")
    fig.update_layout(title=f"{ticker} Monte Carlo Targets", yaxis_title="Price ($)",
        template="plotly_dark", height=360, showlegend=False)
    return fig


def dcf_heatmap(dcf):
    if not dcf.get('available'): return None
    sens = dcf['sensitivity']
    wr = [f"{w*100:.2f}%" for w in dcf['wacc_range']]
    tr = [f"{t*100:.1f}%" for t in dcf['tg_range']]
    z  = [[sens.get(round(w,4), {}).get(tg) or 0 for tg in dcf['tg_range']] for w in dcf['wacc_range']]
    fig = px.imshow(z, x=tr, y=wr, labels=dict(x="Terminal Growth", y="WACC", color="$/share"),
        color_continuous_scale="RdYlGn", text_auto=".0f",
        title="DCF Sensitivity — Intrinsic Value per Share ($)")
    fig.update_layout(template="plotly_dark", height=280, margin=dict(t=40,b=20,l=60,r=20))
    return fig


st.title("📊 Stock Analysis Dashboard")

if not run_btn and not compare_btn:
    st.info("👈 Enter a ticker and click **Run Analysis** to get started.")
    st.markdown("""
    **20+ signals including:**
    - 🖥️ GPU deep learning: LSTM · NHITS · TFT · PatchTST ensemble (RTX 5080)
    - 📰 FinBERT news sentiment · HMM regime · GARCH volatility
    - 💰 3-Stage DCF with sensitivity heatmap · Monte Carlo (10,000 paths)
    - 🏥 Altman Z-Score · Beneish M-Score · Piotroski F-Score
    - 📈 Momentum · Beta decomposition · OBV · Chaikin MF · Amihud liquidity
    """)
    st.stop()


if run_btn:
    with st.spinner(f"Analyzing {ticker}... (GPU signals may take 2-3 min)"):
        try:
            data, scores, mc12, mc36 = run_analysis(ticker, profile, use_gpu)
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()

    sig   = scores['signals']
    price = data['current_price']
    comp  = scores['overall']

    # Header
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Price",          f"${price:.2f}")
    c2.metric("Overall Score",  f"{comp}/100")
    c3.metric("Recommendation", f"{score_emoji(comp)} {score_label(comp)}")
    c4.metric("Sector",         data.get('sector','N/A'))
    c5.metric("Profile",        profile)
    st.divider()

    tabs = st.tabs(["🎯 Overview","📈 Pillars","💰 Valuation","🖥️ GPU / DL",
                    "📊 Monte Carlo","📅 Multi-Horizon","🔬 Deep Signals","📅 Earnings"])

    # TAB 0 — Overview
    with tabs[0]:
        c1,c2 = st.columns([1,1])
        with c1:
            st.subheader("Pillar Radar")
            st.plotly_chart(pillar_radar(scores), use_container_width=True)
        with c2:
            st.subheader("Key Signals")
            rows = [
                ("IV Rank",          f"{sig['ivr']['ivr']}%"),
                ("Altman Z-Score",   f"{sig['distress']['z_score']} ({sig['distress']['risk_level']})"),
                ("Beta vs SPY",      f"{sig['beta']['beta']:.3f}"),
                ("Alpha (ann.)",     f"{sig['beta']['alpha']:+.4f}"),
                ("Earnings Surp.",   f"{sig['earnings']['avg_surprise_pct']:+.1f}%"),
                ("Momentum 6m",      f"{sig['momentum']['momentum_6m']:+.1f}%"),
                ("Momentum 12m",     f"{sig['momentum']['momentum_12m']:+.1f}%"),
                ("Market Regime",    sig['regime']['regime']),
                ("GARCH Vol Ratio",  f"{sig['garch']['vol_ratio']:.2f}"),
                ("RS vs SPY (6mo)",  f"{sig['rs']['rs_spy']:+.1f}%"),
                ("Piotroski",        f"{sig['piotroski']}/9"),
                ("OBV 20d chg",      f"{sig['obv']['obv_change_20d_pct']:+.1f}%"),
            ]
            for k,v in rows:
                st.markdown(f"**{k}:** `{v}`")

    # TAB 1 — Pillars
    with tabs[1]:
        pdf = pd.DataFrame({
            "Pillar":  ["Fundamentals","Technicals","Valuation","Sentiment","ESG/Quality"],
            "Score":   [scores['fundamentals'], scores['technicals'], scores['valuation'],
                        scores['sentiment'], scores['esg_quality']],
        })
        fig = px.bar(pdf, x="Pillar", y="Score", color="Score",
            color_continuous_scale="RdYlGn", range_color=[0,100],
            text="Score", template="plotly_dark", height=340)
        fig.add_hline(y=60, line_dash="dash", annotation_text="Buy threshold (60)")
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
        c1,c2,c3 = st.columns(3)
        with c1:
            st.markdown("**Fundamentals**")
            st.write(f"ROE: {data.get('roe',0):.1f}%")
            st.write(f"Rev growth: {data.get('revenue_growth',0):.1f}%")
            st.write(f"Gross margin: {data.get('gross_margin',0):.1f}%")
            st.write(f"D/E: {data.get('de_ratio',0):.2f}")
        with c2:
            st.markdown("**Technicals**")
            st.write(f"RSI: {data.get('rsi',50):.1f}")
            st.write(f"Above 50MA: {'✅' if data['current_price'] > data.get('ma50',0) else '❌'}")
            st.write(f"Above 200MA: {'✅' if data['current_price'] > data.get('ma200',0) else '❌'}")
            st.write(f"Vol trend: {data.get('vol_trend','N/A')}")
        with c3:
            st.markdown("**Valuation**")
            st.write(f"Fwd P/E: {data.get('forward_pe','N/A')}")
            st.write(f"PEG: {data.get('peg','N/A')}")
            st.write(f"EV/EBITDA: {data.get('ev_ebitda','N/A')}")
            dcf = data.get('dcf',{})
            st.write(f"DCF upside: {dcf.get('upside_pct',0):+.1f}%" if dcf.get('available') else "DCF: N/A")

    # TAB 2 — DCF
    with tabs[2]:
        dcf = data.get('dcf',{})
        if dcf.get('available'):
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Intrinsic Value", f"${dcf['intrinsic']:.2f}")
            c2.metric("Current Price",   f"${price:.2f}")
            c3.metric("DCF Upside",      f"{dcf['upside_pct']:+.1f}%",
                delta_color="normal" if dcf['upside_pct']>0 else "inverse")
            c4.metric("WACC",            f"{dcf['wacc']}%")
            st.caption(f"Stage 1 growth {dcf['g1']}% · Terminal {dcf['terminal_growth']}% · Ke={dcf['ke']}% · Kd={dcf['kd']}%")
            fcfs = dcf['projected_fcfs']
            fig = go.Figure(go.Bar(x=[f"Yr{i+1}" for i in range(len(fcfs))], y=fcfs,
                marker_color='#3b82f6', text=[f"${v}B" for v in fcfs], textposition='outside'))
            fig.update_layout(title="Projected FCF ($B)", template="plotly_dark",
                height=260, yaxis_title="$B", margin=dict(t=40,b=20))
            st.plotly_chart(fig, use_container_width=True)
            hm = dcf_heatmap(dcf)
            if hm: st.plotly_chart(hm, use_container_width=True)
        else:
            st.warning("DCF unavailable — negative or insufficient FCF.")

    # TAB 3 — GPU / DL
    with tabs[3]:
        lstm    = sig.get('lstm', sig.get('lstm_forecast', {}))
        chronos = sig.get('chronos', sig.get('chronos_forecast', {}))
        finbert = sig.get('finbert', sig.get('finbert_sentiment', {}))
        dl      = sig.get('dl_ensemble', sig.get('ensemble_forecast', {}))
        c1,c2,c3,c4 = st.columns(4)
        with c1:
            st.markdown("**LSTM (next-day)**")
            if 'error' not in lstm:
                pred = lstm.get('predicted_return_pct',0)
                d_  = lstm.get('direction','N/A')
                e   = "🟢" if d_=="Bullish" else ("🔴" if d_=="Bearish" else "🟡")
                st.metric("Predicted Return",  f"{pred:+.2f}%")
                st.metric("Direction",         f"{e} {d_}")
                st.metric("Signal Strength",   f"{lstm.get('signal_strength',0):.0f}/100")
                st.caption(f"Device: `{lstm.get('device_used','?')}`")
            else:
                st.warning(lstm.get('error','?'))
        with c2:
            st.markdown("**Chronos-2 (zero-shot, 5-day)**")
            if 'error' not in chronos and 'predicted_return_pct' in chronos:
                p_c = chronos.get('predicted_return_pct', 0)
                d_c = chronos.get('direction', 'N/A')
                e_c = "🟢" if d_c=="Bullish" else ("🔴" if d_c=="Bearish" else "🟡")
                st.metric("5-Day Forecast",  f"{p_c:+.2f}%")
                st.metric("Direction",       f"{e_c} {d_c}")
                st.metric("10th–90th range", f"{chronos.get('lower_10pct',0):+.1f}% to {chronos.get('upper_90pct',0):+.1f}%")
                st.metric("Uncertainty",     f"±{chronos.get('uncertainty_range_pct',0):.1f}%")
                st.metric("Uncertainty",     f"±{chronos.get('uncertainty_pct',0):.2f}%")
                st.caption(f"Device: `{chronos.get('device_used','?')}` | {chronos.get('model','Chronos-2')}")
            else:
                st.warning(chronos.get('error','not installed')[:80])
        with c3:
            st.markdown("**FinBERT (news)**")
            n = finbert.get('num_articles',0)
            if n > 0:
                sc  = finbert.get('sentiment_score',50)
                ov  = finbert.get('overall_sentiment','Neutral')
                e   = "🟢" if sc>=65 else ("🔴" if sc<=35 else "🟡")
                st.metric("Sentiment",   f"{e} {ov}")
                st.metric("Score",       f"{sc:.0f}/100")
                st.metric("Articles",    str(n))
                pos = finbert.get('positive_pct',0)
                neg = finbert.get('negative_pct',0)
                fig = go.Figure(go.Pie(
                    labels=['Positive','Neutral','Negative'],
                    values=[pos, 100-pos-neg, neg],
                    marker_colors=['#22c55e','#94a3b8','#ef4444'], hole=0.4))
                fig.update_layout(height=180, template="plotly_dark",
                    margin=dict(t=0,b=0,l=0,r=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No news available via yfinance.")
        with c4:
            st.markdown("**DL Ensemble (5-day)**")
            if 'error' not in dl and 'predicted_return_pct' in dl:
                p_  = dl.get('predicted_return_pct',0)
                d_  = dl.get('direction','N/A')
                e   = "🟢" if d_=="Bullish" else ("🔴" if d_=="Bearish" else "🟡")
                st.metric("5-Day Forecast",  f"{p_:+.2f}%")
                st.metric("Direction",       f"{e} {d_}")
                st.metric("Uncertainty",     f"±{dl.get('uncertainty_pct',0):.2f}%")
                st.metric("Models",          f"{dl.get('models_used',0)}/5 succeeded")
                st.caption(f"Device: `{dl.get('device_used','?')}`")
                comps = dl.get('components',{})
                if comps:
                    st.markdown("**Model breakdown:**")
                    model_names = {"nhits": "NHITS", "tft": "TFT", "patchtst": "PatchTST", "nbeats": "N-BEATS", "tcn": "TCN"}
                    for nm, label in model_names.items():
                        r = comps.get(nm, {})
                        if 'predicted_return_pct' in r:
                            pred_val = r['predicted_return_pct']
                            em = "📈" if pred_val > 1 else ("📉" if pred_val < -1 else "➡")
                            st.write(f"  {em} **{label}**: `{pred_val:+.2f}%`")
                        elif 'error' in r:
                            st.write(f"  ❌ **{label}**: failed")
            else:
                st.warning(dl.get('error','All models failed')[:80])

    # TAB 4 — Monte Carlo
    with tabs[4]:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Median (12mo)",  f"${mc12['median']:.2f}",
            delta=f"{(mc12['median']/price-1)*100:+.1f}%")
        c2.metric("10th %ile",      f"${mc12['p10']:.2f}",
            delta=f"{(mc12['p10']/price-1)*100:+.1f}%", delta_color="inverse")
        c3.metric("90th %ile",      f"${mc12['p90']:.2f}",
            delta=f"{(mc12['p90']/price-1)*100:+.1f}%")
        c4.metric("P(Gain > 20%)",  f"{mc12['prob_up_20']:.1f}%")
        st.plotly_chart(mc_chart(price, mc12, mc36, ticker), use_container_width=True)
        c1,c2 = st.columns(2)
        c1.metric("P(End below entry)", f"{mc12['prob_negative']:.1f}%",
            delta_color="inverse")
        c2.metric("Stop-loss level (−15%)", f"${mc12['stop_price']:.2f}")
        st.caption(f"σ={data.get('annual_vol',0):.1f}% ann. · μ={mc12['drift']*100:.1f}% (score-derived) · 10,000 paths")

    # TAB 5 — Multi-Horizon (v4.11 — daily time-series)
    with tabs[5]:
        st.subheader("📅 Multi-Horizon Daily Forecasts — 5 SOTA Models (NHITS · TFT · PatchTST · N-BEATS · TCN)")
        multi = sig.get('multi_horizon_forecasts', sig.get('multi_h', {}))
        MODEL_NAMES = ["NHITS", "TFT", "PatchTST", "NBEATS", "TCN"]
        MODEL_COLORS = {"NHITS": "#3b82f6", "TFT": "#f59e0b", "PatchTST": "#22c55e",
                        "NBEATS": "#a855f7", "TCN": "#ef4444"}

        if "error" not in multi and "horizons" in multi:
            horizons = multi["horizons"]
            valid_hs = [h for h in ["5d", "10d", "15d", "20d"] if h in horizons and "error" not in horizons[h]]

            # ── Horizon selector
            sel_h = st.radio("Select horizon for daily chart:", valid_hs, horizontal=True)

            if sel_h and sel_h in horizons:
                hd      = horizons[sel_h]
                daily   = hd.get("daily_forecasts", [])
                pm_d    = hd.get("per_model_daily", {})
                days    = list(range(1, len(daily) + 1))

                # ── Daily time-series chart
                fig_daily = go.Figure()
                # Per-model lines
                for m in MODEL_NAMES:
                    if m in pm_d and pm_d[m]:
                        fig_daily.add_trace(go.Scatter(
                            x=list(range(1, len(pm_d[m]) + 1)),
                            y=pm_d[m],
                            mode="lines",
                            name=m,
                            line=dict(color=MODEL_COLORS[m], width=1.5, dash="dot"),
                            opacity=0.7,
                        ))
                # Ensemble median — bold
                if daily:
                    fig_daily.add_trace(go.Scatter(
                        x=days, y=daily,
                        mode="lines+markers", name="Ensemble Median",
                        line=dict(color="#ffffff", width=3),
                        marker=dict(size=6),
                    ))
                fig_daily.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                fig_daily.update_layout(
                    title=f"Daily Cumulative Return Forecast — {sel_h} Horizon",
                    xaxis_title="Day",
                    yaxis_title="Cumulative Return %",
                    template="plotly_dark", height=420,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_daily, use_container_width=True)

                # ── Day-by-day data table for selected horizon
                if daily and pm_d:
                    tbl_rows = []
                    for i, med in enumerate(daily):
                        row = {"Day": i + 1, "Ensemble Median %": f"{med:+.3f}%"}
                        for m in MODEL_NAMES:
                            v = pm_d[m][i] if m in pm_d and i < len(pm_d[m]) else None
                            row[m] = f"{v:+.3f}%" if v is not None else "N/A"
                        tbl_rows.append(row)
                    with st.expander(f"📋 Day-by-day data table ({sel_h})", expanded=False):
                        st.dataframe(pd.DataFrame(tbl_rows), use_container_width=True, hide_index=True)

            st.divider()

            # ── Horizon summary table (all 4 horizons)
            st.markdown("**Horizon Summary — Final-Day Returns**")
            table_rows = []
            for h in ["5d", "10d", "15d", "20d"]:
                if h not in horizons or "error" in horizons[h]:
                    continue
                h_data  = horizons[h]
                models  = h_data.get("per_model", h_data.get("model_predictions", {}))
                tcn_val = models.get("TCN", 0)
                outlier = "⚠️ TCN" if abs(tcn_val) > 3.0 else ""
                row = {
                    "Horizon":   h,
                    "Median %":  f"{h_data.get('median_return_pct', 0):+.2f}%",
                    "Avg %":     f"{h_data.get('avg_return_pct', 0):+.2f}%",
                    "±Uncert":   f"±{h_data.get('model_disagreement', 0):.2f}%",
                    "Direction": h_data.get("direction", "N/A"),
                }
                for m in MODEL_NAMES:
                    row[m] = f"{models.get(m, 0):+.2f}%" if m in models else "N/A"
                row["Flag"] = outlier
                table_rows.append(row)
            if table_rows:
                st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

            st.success(
                f"**Consensus:** {multi.get('consensus_direction', 'Neutral')}  |  "
                f"**Trend:** {multi.get('trend_signal', 'Stable')}  |  "
                f"Device: `{multi.get('device_used', '?')}`"
            )
            st.caption("Ensemble Median is outlier-robust. TCN flagged when |return| > 3%. "
                       "Returns shown as cumulative % from today's close.")
        else:
            st.warning(f"Multi-horizon data not available: {multi.get('error', 'No data returned')}")

    # TAB 6 — Deep Signals
    with tabs[6]:
        c1,c2 = st.columns(2)
        with c1:
            st.markdown("**🏥 Financial Health**")
            z    = sig['distress']['z_score']
            zone = sig['distress']['risk_level']
            ze   = "🟢" if zone=="Safe" else ("🟡" if zone=="Grey" else "🔴")
            st.metric("Altman Z-Score", f"{z} ({zone})", delta=ze)
            ms   = sig['distress']['m_score']
            st.metric("Beneish M-Score", str(ms),
                delta="OK" if ms<-2.22 else "⚠️ Possible manipulation",
                delta_color="normal" if ms<-2.22 else "inverse")
            st.divider()
            st.markdown("**📐 Beta Decomposition**")
            st.metric("Market Beta",    f"{sig['beta']['beta']:.3f}")
            st.metric("Alpha (ann.)",   f"{sig['beta']['alpha']:+.4f}",
                delta="Outperforming" if sig['beta']['alpha']>0 else "Underperforming",
                delta_color="normal" if sig['beta']['alpha']>0 else "inverse")
            st.metric("R²",             f"{sig['beta']['r_squared']:.3f}")
        with c2:
            st.markdown("**🌊 Liquidity & Quality**")
            st.metric("Piotroski F-Score",    f"{sig['piotroski']}/9")
            st.metric("Amihud Illiquidity",   f"{sig['amihud'].get('amihud',0):.6f}")
            st.metric("Share Turnover",       f"{sig['turnover'].get('turnover',0):.1f}%")
            st.metric("Gross Profitability",  f"{sig['quality']['gross_profitability']:.1f}%")
            st.divider()
            st.markdown("**📡 Regime & Volatility**")
            regime = sig['regime']['regime']
            re = "🟢" if regime=="Bull" else ("🔴" if regime=="Bear" else "🟡")
            st.metric("HMM Regime",        f"{re} {regime}")
            st.metric("GARCH Daily Vol",   f"{sig['garch']['garch_vol_forecast']:.2f}%")
            st.metric("Vol Ratio",         f"{sig['garch']['vol_ratio']:.2f}",
                delta="Calm" if sig['garch']['vol_ratio']<1 else "Elevated",
                delta_color="normal" if sig['garch']['vol_ratio']<1 else "inverse")
            st.divider()
            st.markdown("**📉 Monte Carlo Risk (VaR / CVaR)**")
            mcr = sig.get('mc_risk', {})
            if mcr:
                rl = mcr.get('risk_level', 'N/A')
                re = "🔴" if rl=="High" else ("🟡" if rl=="Medium" else "🟢")
                st.metric("VaR 95% (1yr)",   f"{mcr.get('var_95',0):.1f}%",
                    delta=f"{re} {rl} risk", delta_color="inverse" if rl=="High" else "normal")
                st.metric("CVaR 95% (1yr)",  f"{mcr.get('cvar_95',0):.1f}%")
                st.metric("Simulated Vol",   f"{mcr.get('simulated_annual_vol',0):.1f}%")
                st.metric("Annual Drift",    f"{mcr.get('annual_drift',0):+.1f}%")

    # TAB 7 — Earnings
    with tabs[7]:
        eh = data.get('earnings_history',{})
        if eh and eh.get('quarters'):
            df_e = pd.DataFrame([q for q in eh['quarters'] if q.get('surprise_pct') is not None])
            if not df_e.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_e['date'], y=df_e['surprise_pct'],
                    marker_color=['#22c55e' if v>0 else '#ef4444' for v in df_e['surprise_pct']],
                    text=[f"{v:+.1f}%" for v in df_e['surprise_pct']],
                    textposition='outside', name='EPS Surprise %'))
                if 'drift_5d' in df_e.columns:
                    fig.add_trace(go.Scatter(x=df_e['date'], y=df_e['drift_5d'],
                        mode='lines+markers', name='5-day drift %',
                        line=dict(color='#f59e0b', dash='dot')))
                fig.update_layout(title="EPS Surprise + 5-Day Drift",
                    template="plotly_dark", height=320, yaxis_title="%")
                st.plotly_chart(fig, use_container_width=True)
            c1,c2,c3 = st.columns(3)
            c1.metric("Beat Rate",    f"{eh.get('beat_rate',0):.0f}%")
            c2.metric("Avg Surprise", f"{eh.get('avg_surprise_pct',0):+.1f}%")
            c3.metric("Avg 5d Drift", f"{eh.get('avg_drift_5d',0):+.1f}%")
        else:
            st.info("Earnings history not available.")
        st.divider()
        st.markdown("**📊 Volume Signals**")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("OBV 20d Chg",      f"{sig['obv']['obv_change_20d_pct']:+.1f}%")
        c2.metric("Chaikin MF",        f"{sig['cmf']['cmf']:.3f}", delta=sig['cmf']['cmf_signal'])
        c3.metric("Vol-Price Corr",    f"{sig['vol_price']['vol_price_corr']:.3f}",
            delta=sig['vol_price']['interpretation'])
        c4.metric("Formulaic Alpha",   f"{sig['formulaic_alpha']['alpha']:.3f}",
            delta=sig['formulaic_alpha']['alpha_signal'])


# Compare mode
if compare_btn and compare_tickers:
    tickers_list = [t.strip().upper() for t in compare_tickers.split(',') if t.strip()]
    if len(tickers_list) < 2:
        st.warning("Enter at least 2 tickers.")
    else:
        rows = []
        for t in tickers_list:
            with st.spinner(f"Analyzing {t}..."):
                try:
                    d,s,mc,_ = run_analysis(t, profile, False)
                    rows.append({"Ticker":t, "Price":f"${d['current_price']:.2f}",
                        "Score":s['overall'], "Rec":score_label(s['overall']),
                        "Fundamentals":s['fundamentals'], "Technicals":s['technicals'],
                        "Valuation":s['valuation'], "Sentiment":s['sentiment'],
                        "ESG":s['esg_quality'],
                        "MC Median":f"${mc['median']:.2f}",
                        "MC Ret":f"{(mc['median']/d['current_price']-1)*100:+.1f}%",
                        "P(>20%)":f"{mc['prob_up_20']:.1f}%"})
                except Exception as e:
                    st.error(f"{t}: {e}")
        if rows:
            df_c = pd.DataFrame(rows).set_index('Ticker')
            st.subheader("Comparison")
            st.dataframe(df_c, use_container_width=True)
            fig = px.bar(df_c.reset_index(), x='Ticker', y='Score',
                color='Score', color_continuous_scale='RdYlGn', range_color=[0,100],
                text='Score', template='plotly_dark', height=320, title='Score Comparison')
            fig.add_hline(y=60, line_dash="dash", annotation_text="Buy threshold")
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
