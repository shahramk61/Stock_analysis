"""
3-Stage Discounted Cash Flow (DCF) valuation model.

Stage 1 (Years 1-5):  High growth at analyst/historical rate
Stage 2 (Years 6-10): Linear transition to terminal growth
Stage 3 (Terminal):   Gordon Growth Model terminal value

WACC is calculated via CAPM for equity + after-tax cost of debt.
"""

RISK_FREE_RATE    = 0.045   # 10-yr US Treasury approx
EQUITY_RISK_PREM  = 0.055   # Damodaran ERP estimate
DEFAULT_COST_DEBT = 0.055   # fallback if interest expense unavailable
DEFAULT_TAX_RATE  = 0.21
STAGE1_YEARS      = 5
STAGE2_YEARS      = 5
MAX_STAGE1_GROWTH = 0.30    # cap high-growth assumption at 30%
MIN_STAGE1_GROWTH = 0.03    # floor at 3% (avoid negative projections)


def _calc_wacc(data):
    beta       = data.get('beta') or 1.0
    market_cap = data.get('market_cap') or 1
    total_debt = data.get('total_debt') or data.get('ltdebt') or 0

    ke = RISK_FREE_RATE + beta * EQUITY_RISK_PREM

    # Cost of debt: try interest expense / total debt, else default
    info           = data.get('info', {})
    interest_exp   = abs(info.get('interestExpense') or 0)
    kd = (interest_exp / total_debt) if total_debt > 0 and interest_exp > 0 else DEFAULT_COST_DEBT

    total_capital  = market_cap + total_debt
    we = market_cap  / total_capital
    wd = total_debt  / total_capital

    tax = info.get('effectiveTaxRate') or DEFAULT_TAX_RATE
    wacc = we * ke + wd * kd * (1 - tax)

    # Sanity-check: WACC should be between 5% and 20%
    return round(max(0.05, min(0.20, wacc)), 4), round(ke, 4), round(kd, 4)


def _stage1_growth(data):
    rev_g = (data.get('revenue_growth') or 0) / 100
    eps_g = (data.get('eps_growth') or 0) / 100

    # Take the more conservative of the two; fall back to 10% if both missing
    candidates = [g for g in [rev_g, eps_g] if g > 0]
    g = min(candidates) if candidates else 0.10
    return round(max(MIN_STAGE1_GROWTH, min(MAX_STAGE1_GROWTH, g)), 4)


def _project_fcf(base_fcf, g1, terminal_growth, years1=STAGE1_YEARS, years2=STAGE2_YEARS):
    """Project FCF for each year across all three stages."""
    fcfs = []
    fcf = base_fcf

    # Stage 1
    for _ in range(years1):
        fcf *= (1 + g1)
        fcfs.append(fcf)

    # Stage 2: linear decay from g1 → terminal_growth
    for i in range(1, years2 + 1):
        g = g1 + (terminal_growth - g1) * (i / years2)
        fcf *= (1 + g)
        fcfs.append(fcf)

    return fcfs


def _intrinsic_value(base_fcf, wacc, g1, terminal_growth, shares):
    """Compute intrinsic value per share for given WACC and terminal growth."""
    if wacc <= terminal_growth:
        return None   # Gordon Growth Model undefined

    fcfs = _project_fcf(base_fcf, g1, terminal_growth)

    pv_fcfs = sum(cf / (1 + wacc) ** (t + 1) for t, cf in enumerate(fcfs))

    terminal_fcf = fcfs[-1] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1 + wacc) ** len(fcfs)

    equity_value = pv_fcfs + pv_terminal
    if shares and shares > 0:
        return equity_value / shares
    return None


def calculate_dcf(data, terminal_growth=0.025):
    """
    Run 3-stage DCF. Returns valuation dict with intrinsic value,
    upside %, WACC components, and a sensitivity table.
    """
    shares = data.get('info', {}).get('sharesOutstanding') or \
             data.get('info', {}).get('impliedSharesOutstanding')

    # Base FCF: prefer positive FCF; fall back to operating cash flow * 0.7
    fcf = data.get('fcf')
    op_cf = data.get('op_cashflow')
    if not fcf or fcf <= 0:
        fcf = (op_cf * 0.7) if op_cf and op_cf > 0 else None
    if not fcf or fcf <= 0 or not shares:
        return {'available': False, 'reason': 'Negative or unavailable FCF / share count'}

    wacc, ke, kd = _calc_wacc(data)
    g1 = _stage1_growth(data)
    price = data['current_price']

    intrinsic = _intrinsic_value(fcf, wacc, g1, terminal_growth, shares)
    if intrinsic is None:
        return {'available': False, 'reason': 'WACC ≤ terminal growth rate — model undefined'}

    upside_pct = (intrinsic / price - 1) * 100

    # ── Sensitivity Table ────────────────────────────────────────────────
    # Rows: WACC ± 1% (step 0.5%)
    # Cols: Terminal growth 1.5% / 2.0% / 2.5% / 3.0% / 3.5%
    wacc_range = [wacc - 0.01, wacc - 0.005, wacc, wacc + 0.005, wacc + 0.01]
    tg_range   = [0.015, 0.020, 0.025, 0.030, 0.035]

    sensitivity = {}
    for w in wacc_range:
        row = {}
        for tg in tg_range:
            if w <= tg:
                row[tg] = None
            else:
                iv = _intrinsic_value(fcf, w, g1, tg, shares)
                row[tg] = round(iv, 2) if iv else None
        sensitivity[round(w, 4)] = row

    # Project FCF for display
    projected_fcfs = _project_fcf(fcf, g1, terminal_growth)

    return {
        'available':      True,
        'intrinsic':      round(intrinsic, 2),
        'upside_pct':     round(upside_pct, 1),
        'base_fcf':       round(fcf / 1e9, 2),   # in billions for display
        'g1':             round(g1 * 100, 1),
        'wacc':           round(wacc * 100, 2),
        'ke':             round(ke * 100, 2),
        'kd':             round(kd * 100, 2),
        'terminal_growth': round(terminal_growth * 100, 1),
        'stage1_years':   STAGE1_YEARS,
        'stage2_years':   STAGE2_YEARS,
        'projected_fcfs': [round(f / 1e9, 2) for f in projected_fcfs],  # billions
        'sensitivity':    sensitivity,
        'wacc_range':     wacc_range,
        'tg_range':       tg_range,
    }
