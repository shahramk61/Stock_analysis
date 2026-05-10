import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return float((100 - (100 / (1 + rs))).iloc[-1])


def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])


def calculate_atr(hist, period=14):
    high, low, close = hist['High'], hist['Low'], hist['Close']
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return float(tr.rolling(window=period).mean().iloc[-1])


def get_options_metrics(stock, current_price, hist):
    """Fetch nearest-expiry options chain and compute IVR, skew, P/C ratio."""
    try:
        expirations = stock.options
        if not expirations:
            return None

        today = datetime.now()
        valid_exps = [e for e in expirations
                      if datetime.strptime(e, '%Y-%m-%d') >= today + timedelta(days=7)]
        if not valid_exps:
            return None
        nearest_exp = valid_exps[0]

        chain = stock.option_chain(nearest_exp)
        calls = chain.calls[chain.calls['impliedVolatility'] > 0.01].copy()
        puts  = chain.puts[chain.puts['impliedVolatility']  > 0.01].copy()
        if calls.empty or puts.empty:
            return None

        # ATM strike: closest to current price in the calls chain
        atm_strike = float(calls['strike'].iloc[
            (calls['strike'] - current_price).abs().argsort().iloc[0]
        ])

        atm_call = calls[calls['strike'] == atm_strike]
        atm_put  = puts[puts['strike']  == atm_strike]
        if atm_call.empty or atm_put.empty:
            return None

        atm_call_iv = float(atm_call['impliedVolatility'].values[0]) * 100
        atm_put_iv  = float(atm_put['impliedVolatility'].values[0])  * 100
        avg_atm_iv  = (atm_call_iv + atm_put_iv) / 2

        skew = (atm_put_iv - atm_call_iv) / avg_atm_iv if avg_atm_iv > 0 else 0.0

        put_vol  = float(puts['volume'].fillna(0).sum())
        call_vol = float(calls['volume'].fillna(0).sum())
        pc_ratio = put_vol / call_vol if call_vol > 0 else None

        # IVR: compare current ATM IV to 1-year rolling 30-day realised vol range
        log_ret    = np.log(hist['Close'] / hist['Close'].shift(1)).dropna()
        rolling_rv = log_ret.rolling(30).std() * np.sqrt(252) * 100
        rolling_rv = rolling_rv.dropna().tail(252)

        ivr = None
        if len(rolling_rv) >= 20:
            rv_min, rv_max = float(rolling_rv.min()), float(rolling_rv.max())
            if rv_max > rv_min:
                ivr = max(0.0, min(100.0, (avg_atm_iv - rv_min) / (rv_max - rv_min) * 100))

        ivr_label = ('Extreme — sell vol' if ivr is not None and ivr >= 80 else
                     'High'               if ivr is not None and ivr >= 60 else
                     'Normal'             if ivr is not None and ivr >= 35 else
                     'Low'                if ivr is not None and ivr >= 20 else
                     'Very Low — buy vol' if ivr is not None else 'N/A')

        skew_label = ('Heavy put skew — downside fear' if skew >  0.20 else
                      'Mild put skew'                  if skew >  0.05 else
                      'Neutral'                        if abs(skew) <= 0.05 else
                      'Call skew — bullish sentiment')

        return {
            'expiration':   nearest_exp,
            'atm_strike':   atm_strike,
            'atm_call_iv':  atm_call_iv,
            'atm_put_iv':   atm_put_iv,
            'avg_atm_iv':   avg_atm_iv,
            'skew':         skew,
            'skew_label':   skew_label,
            'pc_ratio':     pc_ratio,
            'ivr':          ivr,
            'ivr_label':    ivr_label,
        }
    except Exception:
        return None


def _count_consecutive_beats(quarters):
    count = 0
    for q in quarters:
        if (q.get('surprise_pct') or -1) > 0:
            count += 1
        else:
            break
    return count


def get_earnings_history(stock, hist, n_quarters=8):
    """Fetch last N quarters of EPS surprise history and 5-day post-earnings drift."""
    try:
        ed = stock.earnings_dates
        if ed is None or ed.empty:
            return None

        # Keep only rows with a reported EPS (past earnings)
        past = ed[ed['Reported EPS'].notna()].head(n_quarters)
        if past.empty:
            return None

        # Normalise history index to tz-naive for comparisons
        h = hist.copy()
        if h.index.tzinfo is not None:
            h.index = h.index.tz_localize(None)

        quarters = []
        for date, row in past.iterrows():
            surprise = row.get('Surprise(%)')
            eps_est  = row.get('EPS Estimate')
            eps_act  = row.get('Reported EPS')

            # Normalise earnings date to tz-naive
            try:
                d_naive = pd.Timestamp(date).tz_localize(None) if date.tzinfo else pd.Timestamp(date)
            except Exception:
                d_naive = None

            drift_5d = None
            if d_naive is not None:
                try:
                    pre    = h[h.index <= d_naive].tail(1)
                    post   = h[h.index  > d_naive].head(5)
                    if not pre.empty and len(post) == 5:
                        drift_5d = round(
                            (float(post['Close'].iloc[-1]) / float(pre['Close'].iloc[-1]) - 1) * 100, 2
                        )
                except Exception:
                    pass

            quarters.append({
                'date':         str(date)[:10],
                'eps_estimate': float(eps_est) if eps_est is not None else None,
                'eps_actual':   float(eps_act) if eps_act is not None else None,
                'surprise_pct': float(surprise) if surprise is not None else None,
                'drift_5d':     drift_5d,
            })

        if not quarters:
            return None

        surprises = [q['surprise_pct'] for q in quarters if q['surprise_pct'] is not None]
        drifts    = [q['drift_5d']     for q in quarters if q['drift_5d']     is not None]
        beats     = sum(1 for s in surprises if s > 0)

        return {
            'quarters':           quarters,
            'n_quarters':         len(quarters),
            'avg_surprise_pct':   round(sum(surprises) / len(surprises), 2) if surprises else None,
            'beat_rate':          round(beats / len(surprises) * 100, 1)    if surprises else None,
            'beats':              beats,
            'misses':             len(surprises) - beats,
            'avg_drift_5d':       round(sum(drifts) / len(drifts), 2)       if drifts    else None,
            'consecutive_beats':  _count_consecutive_beats(quarters),
        }
    except Exception:
        return None


def fetch_stock_data(ticker: str, period="2y"):
    stock = yf.Ticker(ticker)
    info = stock.info
    hist = stock.history(period=period)
    financials = stock.financials        # annual income statement
    balance = stock.balance_sheet        # annual balance sheet
    cashflow = stock.cashflow            # annual cash flow

    closes = hist['Close']
    current_price = float(info.get('currentPrice') or closes.iloc[-1])

    # --- Technicals ---
    rsi = calculate_rsi(closes)
    macd, macd_signal, macd_hist = calculate_macd(closes)
    ma50 = float(closes.rolling(50).mean().iloc[-1])
    ma200 = float(closes.rolling(200).mean().iloc[-1])
    atr = calculate_atr(hist)
    atr_pct = atr / current_price * 100
    annual_vol = float(closes.pct_change().std() * np.sqrt(252) * 100)

    week_52_high = float(closes.tail(252).max())
    week_52_low = float(closes.tail(252).min())
    week_52_pct = (current_price - week_52_low) / (week_52_high - week_52_low + 1e-9) * 100

    # Volume trend: recent 20d avg vs prior 30d avg
    vol_recent = float(hist['Volume'].tail(20).mean())
    vol_prior = float(hist['Volume'].iloc[-50:-20].mean()) if len(hist) > 50 else vol_recent
    vol_trend = "accumulation" if vol_recent > vol_prior * 1.05 else (
                "distribution" if vol_recent < vol_prior * 0.95 else "neutral")

    # --- Fundamentals from financial statements ---
    def safe_get(df, row_keys, col_idx=0):
        for key in row_keys:
            for idx in df.index:
                if key.lower() in str(idx).lower():
                    try:
                        val = df.iloc[df.index.get_loc(idx), col_idx]
                        if pd.notna(val):
                            return float(val)
                    except Exception:
                        pass
        return None

    revenue_now  = safe_get(financials, ['Total Revenue', 'Revenue'])
    revenue_prev = safe_get(financials, ['Total Revenue', 'Revenue'], col_idx=1)
    revenue_growth = (revenue_now / revenue_prev - 1) * 100 if revenue_now and revenue_prev else None

    net_income_now  = safe_get(financials, ['Net Income'])
    net_income_prev = safe_get(financials, ['Net Income'], col_idx=1)

    gross_profit      = safe_get(financials, ['Gross Profit'])
    gross_profit_prev = safe_get(financials, ['Gross Profit'], col_idx=1)
    gross_margin = (gross_profit / revenue_now * 100) if gross_profit and revenue_now else info.get('grossMargins', 0) * 100

    ebit = safe_get(financials, ['EBIT', 'Operating Income'])

    cogs      = safe_get(financials, ['Cost Of Revenue', 'Cost Of Goods Sold'])
    cogs_prev = safe_get(financials, ['Cost Of Revenue', 'Cost Of Goods Sold'], col_idx=1)

    sga      = safe_get(financials, ['Selling General Administrative', 'Selling General And Administration'])
    sga_prev = safe_get(financials, ['Selling General Administrative', 'Selling General And Administration'], col_idx=1)

    op_cashflow = safe_get(cashflow, ['Operating Cash Flow', 'Total Cash From Operating Activities'])
    capex = safe_get(cashflow, ['Capital Expenditure', 'Capital Expenditures'])
    fcf = (op_cashflow + capex) if op_cashflow and capex else info.get('freeCashflow')

    depreciation      = safe_get(cashflow, ['Depreciation And Amortization', 'Depreciation Amortization Depletion'])
    depreciation_prev = safe_get(cashflow, ['Depreciation And Amortization', 'Depreciation Amortization Depletion'], col_idx=1)

    total_debt = safe_get(balance, ['Total Debt', 'Long Term Debt'])
    equity     = safe_get(balance, ['Stockholders Equity', 'Total Stockholder Equity', 'Common Stock Equity'])
    de_ratio = (total_debt / equity) if total_debt and equity and equity != 0 else info.get('debtToEquity', 0) / 100

    # Balance sheet items for Altman Z-Score and Beneish M-Score
    total_assets           = safe_get(balance, ['Total Assets'])
    total_assets_prev      = safe_get(balance, ['Total Assets'], col_idx=1)
    current_assets         = safe_get(balance, ['Current Assets', 'Total Current Assets'])
    current_assets_prev    = safe_get(balance, ['Current Assets', 'Total Current Assets'], col_idx=1)
    current_liabilities    = safe_get(balance, ['Current Liabilities', 'Total Current Liabilities'])
    current_liabilities_prev = safe_get(balance, ['Current Liabilities', 'Total Current Liabilities'], col_idx=1)
    retained_earnings      = safe_get(balance, ['Retained Earnings'])
    total_liabilities      = safe_get(balance, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
    ppe                    = safe_get(balance, ['Net PPE', 'Net Property Plant Equipment'])
    ppe_prev               = safe_get(balance, ['Net PPE', 'Net Property Plant Equipment'], col_idx=1)
    accounts_receivable    = safe_get(balance, ['Accounts Receivable', 'Net Receivables', 'Receivables'])
    accounts_receivable_prev = safe_get(balance, ['Accounts Receivable', 'Net Receivables', 'Receivables'], col_idx=1)
    ltdebt                 = safe_get(balance, ['Long Term Debt', 'Long Term Debt And Capital Lease Obligation'])
    ltdebt_prev            = safe_get(balance, ['Long Term Debt', 'Long Term Debt And Capital Lease Obligation'], col_idx=1)

    market_cap = info.get('marketCap', current_price * info.get('sharesOutstanding', 1))
    fcf_yield = (fcf / market_cap * 100) if fcf and market_cap else None

    roe = info.get('returnOnEquity', 0) * 100
    eps_growth = info.get('earningsGrowth', 0) * 100
    revenue_growth = revenue_growth or (info.get('revenueGrowth', 0) * 100)

    # EPS growth YoY from financials if available
    shares = info.get('sharesOutstanding', 1)
    eps_now = net_income_now / shares if net_income_now and shares else info.get('trailingEps')
    eps_prev = net_income_prev / shares if net_income_prev and shares else None
    if eps_now and eps_prev and eps_prev != 0:
        eps_growth = (eps_now / eps_prev - 1) * 100

    # --- Sentiment ---
    short_pct = (info.get('shortPercentOfFloat') or 0) * 100
    analyst_mean = info.get('recommendationMean', 3.0)   # 1=Strong Buy, 5=Sell
    num_analysts = info.get('numberOfAnalystOpinions', 0)
    target_mean = info.get('targetMeanPrice', current_price)
    target_upside = (target_mean / current_price - 1) * 100

    # --- ESG / Quality proxies ---
    roic = None
    if net_income_now and total_debt and equity:
        invested_capital = total_debt + equity
        roic = (net_income_now / invested_capital * 100) if invested_capital else None

    # Simplified Piotroski F-Score (subset calculable from yfinance)
    f_score = 0
    roa = info.get('returnOnAssets', 0)
    if roa and roa > 0:
        f_score += 1
    if op_cashflow and op_cashflow > 0:
        f_score += 1
    if eps_growth and eps_growth > 0:
        f_score += 1
    if op_cashflow and net_income_now and op_cashflow > net_income_now:
        f_score += 1   # accruals: CF > net income
    if gross_margin and gross_margin > 0:
        f_score += 1
    # Max ~5-6 from available data; scale to 0-9 for reporting

    return {
        'ticker': ticker.upper(),
        'company_name': info.get('longName', ticker.upper()),
        'sector': info.get('sector', 'Unknown'),
        'current_price': current_price,
        'last_updated': datetime.now().strftime("%Y-%m-%d"),

        # Technicals
        'rsi': rsi,
        'macd': macd,
        'macd_signal': macd_signal,
        'macd_hist': macd_hist,
        'ma50': ma50,
        'ma200': ma200,
        'atr': atr,
        'atr_pct': atr_pct,
        'annual_vol': annual_vol,
        'week_52_high': week_52_high,
        'week_52_low': week_52_low,
        'week_52_pct': week_52_pct,
        'vol_trend': vol_trend,
        'beta': info.get('beta', 1.0),

        # Fundamentals
        'revenue_growth': revenue_growth,
        'eps_growth': eps_growth,
        'gross_margin': gross_margin,
        'de_ratio': de_ratio,
        'fcf': fcf,
        'fcf_yield': fcf_yield,
        'roe': roe,

        # Valuation
        'trailing_pe': info.get('trailingPE'),
        'forward_pe': info.get('forwardPE'),
        'peg': info.get('pegRatio'),
        'ps_ratio': info.get('priceToSalesTrailingTwelveMonths'),
        'ev_ebitda': info.get('enterpriseToEbitda'),
        'market_cap': market_cap,

        # Sentiment
        'short_pct': short_pct,
        'analyst_mean': analyst_mean,
        'num_analysts': num_analysts,
        'target_mean': target_mean,
        'target_upside': target_upside,

        # ESG / Quality
        'roic': roic,
        'f_score': f_score,

        # Raw financials for distress scores (Z-Score + M-Score)
        'revenue_now': revenue_now,
        'revenue_prev': revenue_prev,
        'net_income_now': net_income_now,
        'op_cashflow': op_cashflow,
        'ebit': ebit,
        'gross_profit': gross_profit,
        'gross_profit_prev': gross_profit_prev,
        'cogs': cogs,
        'cogs_prev': cogs_prev,
        'sga': sga,
        'sga_prev': sga_prev,
        'depreciation': depreciation,
        'depreciation_prev': depreciation_prev,
        'total_assets': total_assets,
        'total_assets_prev': total_assets_prev,
        'current_assets': current_assets,
        'current_assets_prev': current_assets_prev,
        'current_liabilities': current_liabilities,
        'current_liabilities_prev': current_liabilities_prev,
        'retained_earnings': retained_earnings,
        'total_liabilities': total_liabilities,
        'ppe': ppe,
        'ppe_prev': ppe_prev,
        'accounts_receivable': accounts_receivable,
        'accounts_receivable_prev': accounts_receivable_prev,
        'ltdebt': ltdebt,
        'ltdebt_prev': ltdebt_prev,

        # Earnings history (surprise + post-earnings drift)
        'earnings_history': get_earnings_history(stock, hist),

        # Options metrics
        'options': get_options_metrics(stock, current_price, hist),

        # Raw objects for deep access
        'info': info,
        'history': hist,
    }
