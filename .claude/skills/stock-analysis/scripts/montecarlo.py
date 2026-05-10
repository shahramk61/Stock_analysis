import numpy as np

SCORE_TO_DRIFT = [
    (80, 0.30),
    (65, 0.20),
    (50, 0.10),
    (35, 0.00),
    (0, -0.12),
]


def score_to_drift(composite_score):
    for threshold, drift in SCORE_TO_DRIFT:
        if composite_score >= threshold:
            return drift
    return -0.12


def run_monte_carlo(current_price, annual_vol_pct, composite_score,
                    days=252, paths=10000, stop_loss_pct=0.15):
    """
    Geometric Brownian Motion Monte Carlo simulation.
    annual_vol_pct: annualized volatility as a percentage (e.g. 33 for 33%)
    """
    vol = annual_vol_pct / 100
    drift = score_to_drift(composite_score)
    dt = 1 / 252

    np.random.seed(42)
    Z = np.random.normal(0, 1, size=(paths, days))

    daily_drift = (drift - 0.5 * vol ** 2) * dt
    daily_vol = vol * np.sqrt(dt)

    log_returns = daily_drift + daily_vol * Z
    log_price_paths = np.log(current_price) + np.cumsum(log_returns, axis=1)
    price_paths = np.exp(log_price_paths)

    final_prices = price_paths[:, -1]
    stop_price = current_price * (1 - stop_loss_pct)

    path_mins = price_paths.min(axis=1)

    return {
        'current_price': current_price,
        'drift': drift,
        'vol': vol * 100,
        'days': days,
        'paths': paths,
        'median': float(np.median(final_prices)),
        'p10': float(np.percentile(final_prices, 10)),
        'p90': float(np.percentile(final_prices, 90)),
        'mean': float(np.mean(final_prices)),
        'prob_up_20': float((final_prices > current_price * 1.20).mean() * 100),
        'prob_up_10': float((final_prices > current_price * 1.10).mean() * 100),
        'prob_stop_hit': float((path_mins < stop_price).mean() * 100),
        'prob_negative': float((final_prices < current_price).mean() * 100),
        'stop_price': stop_price,
        'stop_loss_pct': stop_loss_pct * 100,
    }
