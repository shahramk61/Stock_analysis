from datetime import datetime, timedelta


def pct(value, decimals=1):
    if value is None:
        return 'N/A'
    return f"{value:+.{decimals}f}%"


def dollar(value, decimals=2):
    if value is None:
        return 'N/A'
    return f"${value:,.{decimals}f}"


def fmt(value, decimals=2, suffix=''):
    if value is None:
        return 'N/A'
    return f"{value:.{decimals}f}{suffix}"


def generate_report(data, scores, mc_12m, mc_36m, profile, esg_enabled, risk_flags):
    d = data
    p = scores['pillars']
    w = scores['weights']
    composite = scores['composite']
    rating = scores['rating']
    emoji = scores['emoji']

    price = d['current_price']
    atr = d.get('atr', 0)
    stop_loss = price - 2 * atr
    target_price = mc_12m['median']   # MC 12-month median is the price target
    rr_upside = target_price - price
    rr_downside = price - stop_loss
    rr_ratio = rr_upside / rr_downside if rr_downside > 0 else 0

    position_size = (
        '5%' if composite >= 80 and (d.get('beta') or 1) < 1.2 else
        '3%' if composite >= 65 else
        '1.5%' if composite >= 50 else
        '0% (avoid)'
    )

    review_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    lines = []
    a = lines.append

    a(f"# 📊 Stock Analysis: {d['ticker']} — {d['company_name']}")
    a(f"")
    a(f"**Date:** {d['last_updated']}  |  **Price:** {dollar(price)}  |  **Sector:** {d['sector']}")
    a(f"**Investor Profile:** {profile.title()}" + (" + ESG" if esg_enabled else ""))
    a(f"")
    a(f"---")
    a(f"")
    a(f"## Executive Summary")
    a(f"")
    a(f"Composite Score: **{composite}/100 {emoji} → {rating}**")
    a(f"")

    a(f"---")
    a(f"")
    a(f"## Pillar Scores")
    a(f"")
    a(f"| Pillar | Weight | Score | Key Signals |")
    a(f"|---|---|---|---|")
    a(f"| 📈 Fundamentals | {w['fundamentals']*100:.0f}% | {p['fundamentals']} | "
      f"Rev growth {pct(d.get('revenue_growth'))}; EPS growth {pct(d.get('eps_growth'))}; "
      f"Gross margin {fmt(d.get('gross_margin'))}%; D/E {fmt(d.get('de_ratio'))}; "
      f"FCF yield {pct(d.get('fcf_yield'))}; ROE {pct(d.get('roe'))} |")
    ve = p.get('vol_edge')
    ve_str = f"; Vol Edge {ve}/100" if ve is not None else ""
    bd = d.get('beta_decomp', {})
    alpha_str = f"; α={pct(bd.get('alpha_annual'))}/yr" if bd and bd.get('alpha_annual') is not None else ""
    a(f"| 📉 Technicals | {w['technicals']*100:.0f}% | {p['technicals']} | "
      f"RSI {fmt(d.get('rsi'))}; {'Above' if d['current_price'] > d.get('ma50',0) else 'Below'} 50MA ({dollar(d.get('ma50'))}); "
      f"{'Above' if d['current_price'] > d.get('ma200',0) else 'Below'} 200MA ({dollar(d.get('ma200'))}); "
      f"MACD hist {fmt(d.get('macd_hist'))}; Vol {d.get('vol_trend','N/A')}{ve_str}{alpha_str} |")
    _dcf = d.get('dcf', {})
    dcf_str = f"; DCF upside {pct(_dcf.get('upside_pct'))}" if _dcf.get('available') else ''
    a(f"| 💰 Valuation | {w['valuation']*100:.0f}% | {p['valuation']} | "
      f"Fwd P/E {fmt(d.get('forward_pe'))}; PEG {fmt(d.get('peg'))}; "
      f"P/S {fmt(d.get('ps_ratio'))}; EV/EBITDA {fmt(d.get('ev_ebitda'))}; "
      f"52w position {fmt(d.get('week_52_pct'))}%{dcf_str} |")
    eh = d.get('earnings_history', {})
    eh_str = (f"; Beats {eh.get('beats',0)}/{eh.get('n_quarters',0)} qtrs "
              f"(avg {pct(eh.get('avg_surprise_pct'))}); "
              f"avg 5d drift {pct(eh.get('avg_drift_5d'))}"
              if eh and eh.get('avg_surprise_pct') is not None else "")
    a(f"| 🗣 Sentiment | {w['sentiment']*100:.0f}% | {p['sentiment']} | "
      f"Analyst mean {fmt(d.get('analyst_mean'))} ({d.get('num_analysts',0)} analysts); "
      f"Target upside {pct(d.get('target_upside'))}; Short {fmt(d.get('short_pct'))}%{eh_str} |")
    if esg_enabled and p.get('esg') is not None:
        dist = d.get('distress', {})
        z_str = f"Z-Score {fmt(dist.get('z_score'))} ({dist.get('z_zone','N/A')}); " if dist.get('z_score') else ''
        a(f"| 🌱 ESG/Quality | {w.get('esg',0)*100:.0f}% | {p['esg']} | "
          f"{z_str}ROIC {pct(d.get('roic'))}; F-Score {d.get('f_score','N/A')}; ROE {pct(d.get('roe'))} |")
    a(f"")

    formula_parts = ' + '.join(
        f"({w[k]*100:.0f}% × {p[k]})"
        for k in ['fundamentals', 'technicals', 'valuation', 'sentiment']
        if p.get(k) is not None
    )
    if esg_enabled and p.get('esg') is not None:
        formula_parts += f" + ({w.get('esg',0)*100:.0f}% × {p['esg']})"
    a(f"**Composite = {formula_parts} = {composite}/100**")
    a(f"")

    a(f"---")
    a(f"")
    distress = d.get('distress', {})
    z = distress.get('z_score')
    m = distress.get('m_score')
    if z is not None or m is not None:
        a(f"## 🏥 Financial Health")
        a(f"")
        a(f"| Model | Score | Zone | Interpretation |")
        a(f"|---|---|---|---|")
        if z is not None:
            z_zone = distress.get('z_zone', 'N/A')
            z_emoji = '🟢' if z > 2.99 else ('🟡' if z > 1.81 else '🔴')
            a(f"| Altman Z-Score | **{z:.2f}** | {z_emoji} {z_zone} | "
              f"{'Safe — low bankruptcy risk' if z > 2.99 else 'Grey Zone — monitor leverage' if z > 1.81 else 'Distress — elevated bankruptcy risk'} |")
        if m is not None:
            m_zone = distress.get('m_zone', 'N/A')
            m_emoji = '🔴' if m > -2.22 else '🟢'
            a(f"| Beneish M-Score | **{m:.3f}** | {m_emoji} {m_zone} | "
              f"{'Earnings manipulation likely — investigate accruals' if m > -2.22 else 'No manipulation signal detected'} |")
        zc = distress.get('z_components', {})
        mc_ = distress.get('m_components', {})
        if zc:
            a(f"")
            a(f"*Z-Score components: X1(WC/TA)={zc.get('x1','N/A')} · X2(RE/TA)={zc.get('x2','N/A')} · "
              f"X3(EBIT/TA)={zc.get('x3','N/A')} · X4(Mkt/Liab)={zc.get('x4','N/A')} · X5(Rev/TA)={zc.get('x5','N/A')}*")
        if mc_:
            a(f"*M-Score key drivers: DSRI={mc_.get('DSRI','N/A')} · GMI={mc_.get('GMI','N/A')} · "
              f"TATA={mc_.get('TATA','N/A')} · SGI={mc_.get('SGI','N/A')}*")
        a(f"")
    a(f"---")
    a(f"")
    a(f"## Risk Management")
    a(f"")
    a(f"| | |")
    a(f"|---|---|")
    a(f"| 💼 Suggested Position Size | {position_size} |")
    a(f"| 🛑 Stop-Loss | {dollar(stop_loss)} (2× ATR = {dollar(2*atr)}, −{2*d.get('atr_pct',0):.1f}% below entry) |")
    a(f"| 🎯 Price Target | {dollar(target_price)} ({pct((target_price/price-1)*100)}) |")
    rr_str = f"{rr_ratio:.1f}:1 {'✅' if rr_ratio >= 2 else '❌'} {'meets' if rr_ratio >= 2 else 'does NOT meet'} 2:1 minimum"
    a(f"| ⚖️ Risk/Reward | {rr_str} |")
    a(f"")

    a(f"### 🚩 Risk Flags")
    a(f"")
    if risk_flags:
        for flag in risk_flags:
            a(f"- {flag}")
    else:
        a(f"✅ No flags identified")
    a(f"")

    a(f"---")
    a(f"")
    opts = d.get('options')
    ve_score = p.get('vol_edge')
    if opts:
        ivr   = opts.get('ivr')
        skew  = opts.get('skew', 0)
        pc    = opts.get('pc_ratio')

        ivr_emoji  = ('🔴' if ivr is not None and ivr >= 70 else
                      '🟡' if ivr is not None and ivr >= 40 else '🟢')
        skew_emoji = ('🔴' if skew > 0.20 else '🟡' if skew > 0.05 else '🟢')
        pc_emoji   = ('🔴' if pc is not None and pc > 1.3 else
                      '🟢' if pc is not None and pc < 0.7 else '🟡')

        a(f"## 📈 Options Signal" + (f"  (Vol Edge Score: {ve_score}/100)" if ve_score is not None else ""))
        a(f"")
        a(f"| Metric | Value | Signal |")
        a(f"|---|---|---|")
        a(f"| IV Rank (IVR) | {fmt(ivr, 0)}% | {ivr_emoji} {opts.get('ivr_label','N/A')} |")
        a(f"| ATM Call IV | {fmt(opts.get('atm_call_iv'))}% | — |")
        a(f"| ATM Put IV  | {fmt(opts.get('atm_put_iv'))}%  | — |")
        a(f"| Avg ATM IV  | {fmt(opts.get('avg_atm_iv'))}%  | blended into Technicals score |")
        a(f"| Skew (put−call)/avg | {fmt(skew, 3)} | {skew_emoji} {opts.get('skew_label','N/A')} |")
        a(f"| Put/Call Volume Ratio | {fmt(pc) if pc else 'N/A'} | {pc_emoji} {'Bearish (more puts)' if pc and pc > 1.3 else 'Bullish (more calls)' if pc and pc < 0.7 else 'Neutral'} |")
        a(f"")
        a(f"*Expiration: {opts.get('expiration','N/A')} | ATM Strike: {dollar(opts.get('atm_strike'))}*")
        a(f"")
    eh = d.get('earnings_history', {})
    if eh and eh.get('quarters'):
        cb = eh.get('consecutive_beats', 0)
        beat_emoji = '🟢' if eh.get('beat_rate', 0) >= 75 else ('🟡' if eh.get('beat_rate', 0) >= 50 else '🔴')
        drift_avg  = eh.get('avg_drift_5d')
        drift_emoji = '🟢' if drift_avg and drift_avg > 1 else ('🟡' if drift_avg and drift_avg > -1 else '🔴')

        a(f"## 📅 Earnings Surprise History (Last {eh['n_quarters']} Quarters)")
        a(f"")
        a(f"| Quarter | EPS Est. | EPS Actual | Surprise | 5-Day Drift |")
        a(f"|---|---|---|---|---|")
        for q in eh['quarters']:
            s = q.get('surprise_pct')
            s_str = (f"{s:+.1f}% {'✅' if s > 0 else '❌'}" if s is not None else 'N/A')
            dr = q.get('drift_5d')
            dr_str = (f"{dr:+.1f}%" if dr is not None else 'N/A')
            a(f"| {q['date'][:7]} | "
              f"${fmt(q.get('eps_estimate'))} | "
              f"${fmt(q.get('eps_actual'))} | "
              f"{s_str} | {dr_str} |")
        a(f"")
        a(f"**Summary:** {beat_emoji} Beat {eh['beats']}/{eh['n_quarters']} quarters "
          f"({fmt(eh.get('beat_rate'))}% beat rate)  |  "
          f"Avg surprise: {pct(eh.get('avg_surprise_pct'))}  |  "
          f"{drift_emoji} Avg 5-day post-earnings drift: {pct(drift_avg)}")
        if cb >= 3:
            a(f"🔥 **{cb} consecutive beats** — strong execution momentum")
        elif cb == 0:
            a(f"⚠️ Most recent quarter was a miss")
        a(f"")
    a(f"---")
    a(f"")
    bd = d.get('beta_decomp', {})
    if bd and bd.get('market_beta') is not None:
        alpha       = bd.get('alpha_annual', 0)
        market_beta = bd['market_beta']
        sector_beta = bd.get('sector_beta')
        r2          = bd.get('r_squared', 0)
        idio_vol    = bd.get('idio_vol')
        rb30        = bd.get('rolling_30d')
        rb90        = bd.get('rolling_90d')
        rb252       = bd.get('rolling_252d')
        etf         = bd.get('sector_etf', 'N/A')

        alpha_emoji = '🟢' if alpha > 5 else ('🟡' if alpha > 0 else '🔴')
        beta_emoji  = '🟡' if market_beta > 1.5 else '🟢'

        a(f"## 📐 Beta Decomposition (OLS, {bd.get('n_obs', '?')} trading days)")
        a(f"")
        a(f"| Component | Value | Interpretation |")
        a(f"|---|---|---|")
        a(f"| Market Beta (SPY) | {beta_emoji} **{market_beta:.3f}** | "
          f"{'Amplifies' if market_beta > 1 else 'Dampens'} market moves by {abs(market_beta-1)*100:.0f}% |")
        if sector_beta is not None:
            sb_emoji = '🟡' if abs(sector_beta) > 0.5 else '🟢'
            a(f"| Sector Beta ({etf}) | {sb_emoji} **{sector_beta:.3f}** | "
              f"{'Significant' if abs(sector_beta) > 0.3 else 'Low'} sector-specific exposure |")
        a(f"| Annualised Alpha | {alpha_emoji} **{alpha:+.2f}%/yr** | "
          f"{'Outperforms' if alpha > 0 else 'Underperforms'} market+sector by {abs(alpha):.1f}%/yr |")
        a(f"| R² | {fmt(r2*100, 1)}% | {r2*100:.0f}% of price moves explained by market+sector |")
        if idio_vol is not None:
            a(f"| Idiosyncratic Vol | {fmt(idio_vol)}%/yr | Stock-specific annualised risk |")
        a(f"")

        rolls = [x for x in [(30, rb30), (90, rb90), (252, rb252)] if x[1] is not None]
        if rolls:
            trend = ''
            if len(rolls) >= 2 and rolls[0][1] > rolls[-1][1] * 1.1:
                trend = ' ↑ Beta rising (recent sensitivity increasing)'
            elif len(rolls) >= 2 and rolls[0][1] < rolls[-1][1] * 0.9:
                trend = ' ↓ Beta falling (recent sensitivity decreasing)'
            a(f"*Rolling Market Beta: " +
              " | ".join(f"{w}d = {b:.3f}" for w, b in rolls) +
              trend + "*")
        a(f"")
    a(f"---")
    a(f"")
    dcf = d.get('dcf', {})
    if dcf.get('available'):
        iv      = dcf['intrinsic']
        up      = dcf['upside_pct']
        up_emoji = '🟢' if up > 15 else ('🟡' if up > 0 else '🔴')

        a(f"## 💹 DCF Valuation (3-Stage Model)")
        a(f"")
        a(f"| | |")
        a(f"|---|---|")
        a(f"| Intrinsic Value (per share) | **{dollar(iv)}** |")
        a(f"| Current Price | {dollar(price)} |")
        a(f"| DCF Upside / Downside | {up_emoji} **{pct(up)}** |")
        a(f"| Base FCF (TTM) | ${dcf['base_fcf']}B |")
        a(f"")
        a(f"**Assumptions:**  "
          f"Stage 1 growth = {dcf['g1']}% (yrs 1–{dcf['stage1_years']}) → "
          f"transition (yrs {dcf['stage1_years']+1}–{dcf['stage1_years']+dcf['stage2_years']}) → "
          f"terminal = {dcf['terminal_growth']}%  |  "
          f"WACC = {dcf['wacc']}% (Ke={dcf['ke']}%, Kd={dcf['kd']}%)")
        a(f"")

        # Projected FCF table (display years 1, 3, 5, 7, 10)
        fcfs = dcf['projected_fcfs']
        idxs = [0, 2, 4, 6, 9]
        labels = ['Yr 1', 'Yr 3', 'Yr 5', 'Yr 7', 'Yr 10']
        a(f"*Projected FCF ($B): " +
          " · ".join(f"{labels[i]}={fcfs[i]}" for i in range(len(idxs)) if i < len(fcfs)) + "*")
        a(f"")

        # Sensitivity table
        a(f"**Sensitivity Table — Intrinsic Value per Share ($)**")
        a(f"")
        tg_range   = dcf['tg_range']
        wacc_range = dcf['wacc_range']
        sensitivity = dcf['sensitivity']

        header = "| WACC \\ TG | " + " | ".join(f"{tg*100:.1f}%" for tg in tg_range) + " |"
        sep    = "|" + "---|" * (len(tg_range) + 1)
        a(header)
        a(sep)
        for w in wacc_range:
            row = sensitivity.get(round(w, 4), {})
            cells = []
            for tg in tg_range:
                val = row.get(tg)
                if val is None:
                    cells.append('N/A')
                else:
                    marker = ' ◄' if abs(w - dcf['wacc']/100) < 0.001 and abs(tg - dcf['terminal_growth']/100) < 0.001 else ''
                    cells.append(f"${val:.0f}{marker}")
            bold = '**' if abs(w - dcf['wacc']/100) < 0.001 else ''
            a(f"| {bold}{w*100:.2f}%{bold} | " + " | ".join(cells) + " |")
        a(f"")
        a(f"*◄ = base case. Values below current price ({dollar(price)}) shaded as downside.*")
        a(f"")
    a(f"---")
    a(f"")
    a(f"## 📊 Monte Carlo Simulation (10,000 paths, GBM)")
    a(f"")
    a(f"**Inputs:** Price={dollar(price)} | σ={fmt(d.get('annual_vol'))}% annualized | μ={pct(mc_12m['drift']*100)} (score-derived) | Stop={dollar(mc_12m['stop_price'])} (−{fmt(mc_12m['stop_loss_pct'])}%)")
    a(f"")
    a(f"### Intermediate Horizon (12 months)")
    a(f"")
    a(f"| Scenario | Price | Return |")
    a(f"|---|---|---|")
    a(f"| Median | {dollar(mc_12m['median'])} | {pct((mc_12m['median']/price-1)*100)} |")
    a(f"| 10th Percentile (downside) | {dollar(mc_12m['p10'])} | {pct((mc_12m['p10']/price-1)*100)} |")
    a(f"| 90th Percentile (upside) | {dollar(mc_12m['p90'])} | {pct((mc_12m['p90']/price-1)*100)} |")
    a(f"")
    a(f"| Probability | |")
    a(f"|---|---|")
    a(f"| Gain > +20% | {fmt(mc_12m['prob_up_20'])}% |")
    a(f"| Gain > +10% | {fmt(mc_12m['prob_up_10'])}% |")
    a(f"| Stop-loss hit (path-dependent) | {fmt(mc_12m['prob_stop_hit'])}% |")
    a(f"| End below current price | {fmt(mc_12m['prob_negative'])}% |")
    a(f"")
    a(f"### Long-term Horizon (36 months)")
    a(f"")
    a(f"| Scenario | Price | Return |")
    a(f"|---|---|---|")
    a(f"| Median | {dollar(mc_36m['median'])} | {pct((mc_36m['median']/price-1)*100)} |")
    a(f"| 10th Percentile (downside) | {dollar(mc_36m['p10'])} | {pct((mc_36m['p10']/price-1)*100)} |")
    a(f"| 90th Percentile (upside) | {dollar(mc_36m['p90'])} | {pct((mc_36m['p90']/price-1)*100)} |")
    a(f"")
    a(f"> ⚠️ Simulation uses historical volatility and score-derived drift. Not a precise forecast.")
    a(f"")

    a(f"---")
    a(f"")
    a(f"## Multi-Horizon Recommendations")
    a(f"")
    a(f"| Horizon | Rating | MC Median | Rationale |")
    a(f"|---|---|---|---|")
    swing = 'Buy' if p['technicals'] >= 65 else ('Hold' if p['technicals'] >= 50 else 'Avoid')
    inter = rating
    longterm = 'Buy' if composite >= 60 else ('Hold' if composite >= 45 else 'Avoid')
    a(f"| 🏃 Swing (1–3 mo) | {swing} | N/A | Technicals score {p['technicals']}/100 |")
    a(f"| 📈 Intermediate (6–18 mo) | {inter} | {dollar(mc_12m['median'])} ({pct((mc_12m['median']/price-1)*100)}) | Composite {composite}/100 |")
    a(f"| 🏦 Long-term (3+ yr) | {longterm} | {dollar(mc_36m['median'])} ({pct((mc_36m['median']/price-1)*100)}) | Business quality + moat thesis |")
    a(f"")

    a(f"---")
    a(f"")
    a(f"## 📋 Alert Checklist")
    a(f"")
    a(f"| Trigger | Action |")
    a(f"|---|---|")
    a(f"| Price reaches {dollar(target_price)} | Re-analyze for exit / add |")
    a(f"| Price drops to {dollar(stop_loss)} | Review stop-loss decision |")
    a(f"| Composite score drops below {max(0, composite-10):.0f} | Reassess thesis |")
    a(f"| Review again by | {review_date} |")
    a(f"")

    a(f"---")
    a(f"")
    a(f"## Data Sources")
    a(f"")
    a(f"- yfinance {d['last_updated']}: price, financials, analyst data, short interest")
    a(f"- Monte Carlo: 10,000-path GBM simulation (numpy, seed=42)")
    a(f"")
    a(f"---")
    a(f"")
    a(f"*Generated by stock-analysis Claude Code skill v4.1 — {d['last_updated']}*")
    a(f"*For informational purposes only. Not financial advice. Verify all data before trading.*")

    return '\n'.join(lines)
