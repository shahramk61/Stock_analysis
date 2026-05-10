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

    return round((rsi_score + ma_score + macd_score + vol_score + atr_score) / 5)


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

    scores = [s for s in [fpe_score, peg_score, ps_score, ev_score, w52_score] if s is not None]
    return round(sum(scores) / len(scores)) if scores else 50


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

    return round((analyst_score + target_score + short_score) / 3)


def score_esg(d):
    roic = d.get('roic')
    roic_score = (90 if roic and roic > 20 else
                  80 if roic and roic > 15 else
                  65 if roic and roic > 10 else
                  50 if roic and roic > 5 else
                  30 if roic else 50)

    f = d.get('f_score', 3)
    f_score = min(100, int(f / 6 * 100))  # scaled from partial F-score

    roe = d.get('roe', 0)
    roe_score = (90 if roe > 25 else
                 75 if roe > 15 else
                 60 if roe > 10 else 40)

    return round((roic_score + f_score + roe_score) / 3)


def calculate_pillars(data, profile='balanced', esg_enabled=True):
    weights = PROFILES.get(profile.lower(), PROFILES['balanced'])
    if not esg_enabled:
        # redistribute ESG weight proportionally to other pillars
        esg_w = weights['esg']
        total_other = 1 - esg_w
        weights = {k: v / total_other for k, v in weights.items() if k != 'esg'}
        weights['esg'] = 0

    pillars = {
        'fundamentals': score_fundamentals(data),
        'technicals':   score_technicals(data),
        'valuation':    score_valuation(data),
        'sentiment':    score_sentiment(data),
        'esg':          score_esg(data) if esg_enabled else None,
    }

    composite = sum(
        pillars[k] * weights.get(k, 0)
        for k in pillars if pillars[k] is not None
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
    return flags
