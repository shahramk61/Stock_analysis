PROFILES = {
    'balanced':  {'fundamentals': 0.33, 'technicals': 0.23, 'valuation': 0.23, 'sentiment': 0.13, 'esg': 0.08},
    'value':     {'fundamentals': 0.38, 'technicals': 0.13, 'valuation': 0.33, 'sentiment': 0.08, 'esg': 0.08},
    'growth':    {'fundamentals': 0.38, 'technicals': 0.18, 'valuation': 0.18, 'sentiment': 0.18, 'esg': 0.08},
    'momentum':  {'fundamentals': 0.18, 'technicals': 0.38, 'valuation': 0.18, 'sentiment': 0.18, 'esg': 0.08},
    'income':    {'fundamentals': 0.33, 'technicals': 0.18, 'valuation': 0.28, 'sentiment': 0.13, 'esg': 0.08},
}

SCORE_BANDS = [
    (80, 'Strong Buy', '🟢🟢'),
    (65, 'Buy',        '🟢'),
    (50, 'Hold/Watch', '🟡'),
    (35, 'Caution',    '🔴'),
    (0,  'Avoid',      '🔴🔴'),
]


def _band(value, breakpoints):
    """Map a raw value to a 0-100 score using (threshold, score) breakpoints (descending order)."""
    for threshold, score in breakpoints:
        if value is not None and value >= threshold:
            return score
    return breakpoints[-1][1] if breakpoints else 50


def score_fundamentals(d):
    rev = _band(d.get('revenue_growth'), [
        (20, 95), (15, 85), (10, 75), (5, 60), (0, 45), (-999, 20)
    ])
    eps = _band(d.get('eps_growth'), [
        (25, 95), (15, 85), (10, 75), (5, 60), (0, 45), (-999, 20)
    ])
    gm = _band(d.get('gross_margin'), [
        (50, 95), (40, 85), (30, 70), (20, 55), (0, 30)
    ])
    de = d.get('de_ratio')
    de_score = (95 if de is None else
                95 if de < 0.3 else
                85 if de < 0.5 else
                75 if de < 1.0 else
                55 if de < 2.0 else 20)
    fcf_score = _band(d.get('fcf_yield'), [
        (5, 90), (3, 80), (1, 65), (0, 50), (-999, 15)
    ])
    roe = _band(d.get('roe'), [
        (30, 95), (20, 85), (15, 75), (10, 60), (0, 35)
    ])
    scores = [s for s in [rev, eps, gm, de_score, fcf_score, roe] if s is not None]
    return round(sum(scores) / len(scores)) if scores else 50


def score_volatility_edge(opts):
    """Score options signals 0-100. High score = favorable vol environment for longs."""
    if opts is None:
        return None

    ivr = opts.get('ivr', 50)
    # Low IVR = cheap options, less fear priced in = bullish
    # High IVR = expensive vol, market fear = bearish for longs
    ivr_score = (85 if ivr is not None and ivr < 20 else
                 75 if ivr is not None and ivr < 35 else
                 60 if ivr is not None and ivr < 55 else
                 45 if ivr is not None and ivr < 70 else
                 30 if ivr is not None and ivr < 85 else
                 20 if ivr is not None else 50)

    skew = opts.get('skew', 0)
    # Neutral skew is healthy; heavy put skew signals fear/downside concern
    skew_score = (75 if skew < -0.05 else          # call skew: mild bullish
                  68 if abs(skew) <= 0.05 else      # neutral
                  58 if 0.05 < skew <= 0.15 else    # mild put skew: normal
                  42 if 0.15 < skew <= 0.30 else    # moderate: caution
                  25)                               # heavy put skew: fear

    pc = opts.get('pc_ratio')
    # Low P/C = more calls = bullish; high P/C = more puts = bearish
    pc_score = (82 if pc is not None and pc < 0.5 else
                72 if pc is not None and pc < 0.7 else
                60 if pc is not None and pc < 1.0 else
                48 if pc is not None and pc < 1.3 else
                32 if pc is not None else 50)

    return round((ivr_score + skew_score + pc_score) / 3)


def score_technicals(d):
    rsi = d.get('rsi', 50)
    rsi_score = (70 if 40 <= rsi <= 60 else
                 80 if 30 <= rsi < 40 else
                 65 if 60 < rsi <= 70 else
                 50 if 70 < rsi <= 75 else
                 25 if rsi > 75 else
                 40 if rsi < 30 else 50)

    price = d['current_price']
    ma50, ma200 = d.get('ma50', price), d.get('ma200', price)
    above_50 = price > ma50
    above_200 = price > ma200
    ma_score = (85 if above_50 and above_200 else
                55 if above_200 else
                40 if above_50 else 25)

    macd_hist = d.get('macd_hist', 0)
    macd_score = (85 if macd_hist > 0.5 else
                  70 if macd_hist > 0 else
                  55 if macd_hist > -0.5 else 35)

    vol_score = {'accumulation': 75, 'neutral': 55, 'distribution': 35}.get(d.get('vol_trend', 'neutral'), 55)

    atr_pct = d.get('atr_pct', 2)
    atr_score = (70 if 1 <= atr_pct <= 3 else
                 60 if 3 < atr_pct <= 5 else
                 40 if atr_pct > 5 else 65)

    base = round((rsi_score + ma_score + macd_score + vol_score + atr_score) / 5)

    # Blend in volatility edge (20% weight) when options data is available
    ve = score_volatility_edge(d.get('options'))
    if ve is not None:
        return round(0.80 * base + 0.20 * ve)
    return base


def score_valuation(d):
    fwd_pe = _band(d.get('forward_pe'), [
        (0.01, None)  # placeholder
    ])
    fpe = d.get('forward_pe')
    fpe_score = (90 if fpe and fpe < 15 else
                 80 if fpe and fpe < 20 else
                 70 if fpe and fpe < 25 else
                 55 if fpe and fpe < 30 else
                 40 if fpe and fpe < 35 else
                 25 if fpe else 50)

    peg = d.get('peg')
    peg_score = (90 if peg and peg < 1.0 else
                 75 if peg and peg < 1.5 else
                 60 if peg and peg < 2.0 else
                 45 if peg and peg < 2.5 else
                 25 if peg else 50)

    ps = d.get('ps_ratio')
    ps_score = (90 if ps and ps < 2 else
                80 if ps and ps < 4 else
                65 if ps and ps < 6 else
                45 if ps and ps < 10 else
                25 if ps else 50)

    ev = d.get('ev_ebitda')
    ev_score = (90 if ev and ev < 10 else
                75 if ev and ev < 15 else
                60 if ev and ev < 20 else
                45 if ev and ev < 25 else
                25 if ev else 50)

    w52 = d.get('week_52_pct', 50)
    w52_score = (80 if w52 < 20 else
                 75 if w52 < 40 else
                 65 if w52 < 60 else
                 50 if w52 < 80 else 30)

    # DCF-implied upside (from 3-stage model if available)
    dcf = d.get('dcf', {})
    dcf_upside = dcf.get('upside_pct') if dcf.get('available') else None
    dcf_score = (95 if dcf_upside is not None and dcf_upside > 40 else
                 85 if dcf_upside is not None and dcf_upside > 25 else
                 75 if dcf_upside is not None and dcf_upside > 10 else
                 60 if dcf_upside is not None and dcf_upside > 0  else
                 35 if dcf_upside is not None and dcf_upside > -15 else
                 15 if dcf_upside is not None else None)

    scores = [s for s in [fpe_score, peg_score, ps_score, ev_score, w52_score, dcf_score] if s is not None]
    return round(sum(scores) / len(scores)) if scores else 50


def score_earnings_history(earnings):
    """Score based on EPS surprise history and post-earnings drift."""
    if not earnings or earnings.get('avg_surprise_pct') is None:
        return None

    avg_surprise = earnings['avg_surprise_pct']
    beat_rate    = earnings.get('beat_rate') or 50
    avg_drift    = earnings.get('avg_drift_5d') or 0

    surprise_score = (90 if avg_surprise > 10 else
                      80 if avg_surprise >  5 else
                      70 if avg_surprise >  2 else
                      55 if avg_surprise >  0 else
                      35 if avg_surprise > -3 else 15)

    beat_score = (90 if beat_rate >= 90 else
                  80 if beat_rate >= 75 else
                  65 if beat_rate >= 50 else
                  40 if beat_rate >= 25 else 20)

    drift_score = (85 if avg_drift >  3 else
                   70 if avg_drift >  1 else
                   55 if avg_drift > -1 else
                   35 if avg_drift > -3 else 20)

    return round((surprise_score + beat_score + drift_score) / 3)


def score_sentiment(d):
    mean = d.get('analyst_mean', 3.0)
    analyst_score = (90 if mean <= 1.5 else
                     80 if mean <= 2.0 else
                     65 if mean <= 2.5 else
                     50 if mean <= 3.0 else 25)

    upside = d.get('target_upside', 0)
    target_score = (90 if upside > 30 else
                    80 if upside > 20 else
                    70 if upside > 10 else
                    55 if upside > 5 else
                    35 if upside > 0 else 10)

    short = d.get('short_pct', 5)
    short_score = (90 if short < 1 else
                   80 if short < 5 else
                   65 if short < 10 else
                   40 if short < 20 else 20)

    # Earnings surprise history (blended in when available)
    earnings_score = score_earnings_history(d.get('earnings_history'))

    scores = [analyst_score, target_score, short_score]
    if earnings_score is not None:
        scores.append(earnings_score)
    return round(sum(scores) / len(scores))


def calculate_distress_scores(d):
    """
    Altman Z-Score (bankruptcy risk) and Beneish M-Score (earnings manipulation).
    Returns dict with scores, zones, and component values.
    """
    def safe_div(a, b):
        return a / b if a is not None and b and b != 0 else None

    # ── Altman Z-Score ──────────────────────────────────────────────────
    z_score = None
    z_zone  = None
    z_components = {}

    ta = d.get('total_assets')
    if ta and ta > 0:
        try:
            ca  = d.get('current_assets')  or 0
            cl  = d.get('current_liabilities') or 0
            re  = d.get('retained_earnings') or 0
            tl  = d.get('total_liabilities') or 1
            rev = d.get('revenue_now') or d.get('info', {}).get('totalRevenue')
            ebit = d.get('ebit') or 0
            mc   = d.get('market_cap') or 0

            x1 = (ca - cl) / ta                    # Working Capital / Total Assets
            x2 = re / ta                            # Retained Earnings / Total Assets
            x3 = ebit / ta                          # EBIT / Total Assets
            x4 = mc / tl if tl else 0              # Market Cap / Total Liabilities
            x5 = rev / ta if rev else 0             # Revenue / Total Assets

            z_score = round(1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5, 2)
            z_zone  = ('Safe'     if z_score > 2.99 else
                       'Grey Zone' if z_score > 1.81 else
                       'Distress')
            z_components = {'x1': round(x1,3), 'x2': round(x2,3),
                            'x3': round(x3,3), 'x4': round(x4,3), 'x5': round(x5,3)}
        except Exception:
            pass

    # ── Beneish M-Score ─────────────────────────────────────────────────
    m_score = None
    m_zone  = None
    m_components = {}

    ta_t  = d.get('total_assets')
    ta_t1 = d.get('total_assets_prev')
    rev_t  = d.get('revenue_now')
    rev_t1 = d.get('revenue_prev')

    if ta_t and ta_t1 and ta_t > 0 and ta_t1 > 0 and rev_t and rev_t1:
        try:
            ar_t  = d.get('accounts_receivable') or 0
            ar_t1 = d.get('accounts_receivable_prev') or 0
            gp_t  = d.get('gross_profit') or 0
            gp_t1 = d.get('gross_profit_prev') or 0
            ca_t  = d.get('current_assets') or 0
            ca_t1 = d.get('current_assets_prev') or 0
            ppe_t  = d.get('ppe') or 0
            ppe_t1 = d.get('ppe_prev') or 0
            dep_t  = abs(d.get('depreciation') or 1)
            dep_t1 = abs(d.get('depreciation_prev') or dep_t)
            sga_t  = abs(d.get('sga') or 0)
            sga_t1 = abs(d.get('sga_prev') or sga_t)
            ni_t   = d.get('net_income_now') or 0
            cfo_t  = d.get('op_cashflow') or 0
            cl_t   = d.get('current_liabilities') or 0
            cl_t1  = d.get('current_liabilities_prev') or 0
            ltd_t  = d.get('ltdebt') or 0
            ltd_t1 = d.get('ltdebt_prev') or 0

            # Days Sales Receivable Index
            dsri = safe_div(ar_t / rev_t, ar_t1 / rev_t1) if rev_t1 else 1.0
            # Gross Margin Index
            gmi = safe_div(gp_t1 / rev_t1, gp_t / rev_t) if (gp_t and gp_t1) else 1.0
            # Asset Quality Index: non-current non-PPE assets / total assets
            aq_t  = 1 - safe_div(ca_t  + ppe_t,  ta_t)  if ta_t  else 0
            aq_t1 = 1 - safe_div(ca_t1 + ppe_t1, ta_t1) if ta_t1 else 0
            aqi = safe_div(aq_t, aq_t1) if aq_t1 else 1.0
            # Sales Growth Index
            sgi = rev_t / rev_t1
            # Depreciation Index
            dep_rate_t  = dep_t  / (ppe_t  + dep_t)  if (ppe_t  + dep_t)  > 0 else 0
            dep_rate_t1 = dep_t1 / (ppe_t1 + dep_t1) if (ppe_t1 + dep_t1) > 0 else dep_rate_t
            depi = safe_div(dep_rate_t1, dep_rate_t) if dep_rate_t else 1.0
            # SGA Index
            sgai = safe_div(sga_t / rev_t, sga_t1 / rev_t1) if (sga_t and sga_t1 and rev_t1) else 1.0
            # Total Accruals to Total Assets
            tata = (ni_t - cfo_t) / ta_t
            # Leverage Index
            lev_t  = (ltd_t  + cl_t)  / ta_t
            lev_t1 = (ltd_t1 + cl_t1) / ta_t1 if ta_t1 else lev_t
            lvgi = safe_div(lev_t, lev_t1) if lev_t1 else 1.0

            # Replace any None with neutral 1.0
            vars_ = [dsri, gmi, aqi, sgi, depi, sgai, tata, lvgi]
            dsri, gmi, aqi, sgi, depi, sgai, tata, lvgi = [v if v is not None else 1.0 for v in vars_]

            m_score = round(
                -4.84 + 0.920*dsri + 0.528*gmi + 0.404*aqi + 0.892*sgi
                + 0.115*depi - 0.172*sgai + 4.679*tata - 0.327*lvgi, 3
            )
            m_zone = 'Possible Manipulator' if m_score > -2.22 else 'Non-Manipulator'
            m_components = {
                'DSRI': round(dsri, 3), 'GMI': round(gmi, 3),
                'AQI': round(aqi, 3),  'SGI': round(sgi, 3),
                'DEPI': round(depi, 3), 'SGAI': round(sgai, 3),
                'TATA': round(tata, 4), 'LVGI': round(lvgi, 3),
            }
        except Exception:
            pass

    return {
        'z_score': z_score,
        'z_zone':  z_zone,
        'z_components': z_components,
        'm_score': m_score,
        'm_zone':  m_zone,
        'm_components': m_components,
    }


def score_esg(d):
    roic = d.get('roic')
    roic_score = (90 if roic and roic > 20 else
                  80 if roic and roic > 15 else
                  65 if roic and roic > 10 else
                  50 if roic and roic > 5 else
                  30 if roic else 50)

    f = d.get('f_score', 3)
    f_score = min(100, int(f / 6 * 100))

    roe = d.get('roe', 0)
    roe_score = (90 if roe > 25 else
                 75 if roe > 15 else
                 60 if roe > 10 else 40)

    # Incorporate Altman Z-Score into ESG/Quality pillar
    distress = d.get('distress', {})
    z = distress.get('z_score')
    z_score_val = (90 if z is not None and z > 3.5 else
                   75 if z is not None and z > 2.99 else
                   55 if z is not None and z > 1.81 else
                   20 if z is not None else 50)

    scores = [roic_score, f_score, roe_score, z_score_val]
    return round(sum(scores) / len(scores))


def calculate_pillars(data, profile='balanced', esg_enabled=True):
    # Compute distress scores once and store in data for use across scorers
    data['distress'] = calculate_distress_scores(data)

    weights = PROFILES.get(profile.lower(), PROFILES['balanced'])
    if not esg_enabled:
        # redistribute ESG weight proportionally to other pillars
        esg_w = weights['esg']
        total_other = 1 - esg_w
        weights = {k: v / total_other for k, v in weights.items() if k != 'esg'}
        weights['esg'] = 0

    pillars = {
        'fundamentals': score_fundamentals(data),
        'technicals':   score_technicals(data),   # includes 20% vol-edge blend
        'valuation':    score_valuation(data),
        'sentiment':    score_sentiment(data),
        'esg':          score_esg(data) if esg_enabled else None,
        'vol_edge':     score_volatility_edge(data.get('options')),  # display only
    }

    composite = sum(
        pillars[k] * weights.get(k, 0)
        for k in pillars
        if pillars[k] is not None and k != 'vol_edge'  # vol_edge is display-only
    )

    rating_label, rating_emoji = 'Hold/Watch', '🟡'
    for threshold, label, emoji in SCORE_BANDS:
        if composite >= threshold:
            rating_label, rating_emoji = label, emoji
            break

    return {
        'pillars': pillars,
        'weights': weights,
        'composite': round(composite, 1),
        'rating': rating_label,
        'emoji': rating_emoji,
    }


def check_risk_flags(data):
    flags = []
    if (data.get('de_ratio') or 0) > 2.0:
        flags.append('⚠️  Debt/Equity > 2.0')
    if (data.get('fcf_yield') or 1) < 0:
        flags.append('⚠️  Negative Free Cash Flow')
    rsi = data.get('rsi', 50)
    if rsi > 75:
        flags.append(f'⚠️  RSI overbought ({rsi:.1f})')
    elif rsi < 25:
        flags.append(f'⚠️  RSI oversold ({rsi:.1f})')
    if (data.get('beta') or 1) > 2.0:
        flags.append(f'⚠️  High beta ({data["beta"]:.2f})')
    if (data.get('short_pct') or 0) > 20:
        flags.append(f'⚠️  Short interest > 20% ({data["short_pct"]:.1f}%)')

    eh = data.get('earnings_history', {})
    if eh:
        misses = eh.get('misses', 0)
        n = eh.get('n_quarters', 0)
        if n >= 2 and misses >= 2 and (misses / n) >= 0.5:
            flags.append(f'⚠️  Earnings misses in {misses}/{n} recent quarters — weak execution')
        avg_drift = eh.get('avg_drift_5d')
        if avg_drift is not None and avg_drift < -3:
            flags.append(f'⚠️  Avg 5-day post-earnings drift {avg_drift:+.1f}% — market consistently disappointed')

    distress = data.get('distress', {})
    z = distress.get('z_score')
    if z is not None:
        if z < 1.81:
            flags.append(f'🚨 Altman Z-Score {z:.2f} — DISTRESS ZONE (bankruptcy risk elevated)')
        elif z < 2.99:
            flags.append(f'⚠️  Altman Z-Score {z:.2f} — Grey Zone (monitor closely)')
    m = distress.get('m_score')
    if m is not None and m > -2.22:
        flags.append(f'🚨 Beneish M-Score {m:.3f} — Possible earnings manipulation (threshold: −2.22)')

    opts = data.get('options')
    if opts:
        ivr = opts.get('ivr')
        if ivr is not None and ivr >= 80:
            flags.append(f'⚠️  IV Rank {ivr:.0f}% — very expensive options, elevated fear')
        if opts.get('skew', 0) > 0.25:
            flags.append(f'⚠️  Heavy put skew ({opts["skew"]:.2f}) — significant downside fear priced in')
        pc = opts.get('pc_ratio')
        if pc is not None and pc > 1.5:
            flags.append(f'⚠️  Put/Call ratio {pc:.2f} — heavy put buying, bearish signal')

    return flags
