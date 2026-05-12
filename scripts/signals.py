def get_chronos_forecast(ticker: str, prediction_length: int = 5, use_covariates: bool = True):
    """
    Chronos-2 forecast with optional covariates (Volume + RSI + ATR).
    This makes the model use multiple features instead of just Close price.
    """
    try:
        from chronos import Chronos2Pipeline
        import pandas_ta as ta
        device_map = "cuda" if torch.cuda.is_available() else "cpu"
        pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=device_map)

        hist = yf.Ticker(ticker).history(period="2y")
        if len(hist) < 80:
            return {"error": "Insufficient data"}

        df = hist[['Close', 'Volume']].dropna().copy()
        df['rsi'] = ta.rsi(df['Close'], length=14)
        df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        df = df.dropna()

        if len(df) < 60:
            return {"error": "Insufficient data after indicators"}

        # Use last 120 rows for context
        context_df = df[['Close', 'Volume', 'rsi', 'atr']].tail(120)
        last_price = float(context_df['Close'].iloc[-1])

        # Convert to list of lists for Chronos-2 (target + covariates)
        context = context_df.values.tolist()

        # Predict with covariates
        forecast = pipeline.predict(
            context=context,
            prediction_length=prediction_length,
            quantile_levels=[0.1, 0.5, 0.9]
        )

        q10_arr = np.atleast_1d(forecast[0].cpu().numpy())
        q50_arr = np.atleast_1d(forecast[1].cpu().numpy())
        q90_arr = np.atleast_1d(forecast[2].cpu().numpy())

        # Daily cumulative returns
        daily_returns_q50 = [round(float((float(p) - last_price) / last_price * 100), 3) for p in q50_arr]
        daily_returns_q10 = [round(float((float(p) - last_price) / last_price * 100), 3) for p in q10_arr]
        daily_returns_q90 = [round(float((float(p) - last_price) / last_price * 100), 3) for p in q90_arr]
        daily_prices_q50 = [round(float(p), 2) for p in q50_arr]

        pred_return = daily_returns_q50[-1] if daily_returns_q50 else 0.0
        direction = "Bullish 📈" if pred_return > 1.0 else "Bearish 📉" if pred_return < -1.0 else "Neutral ➕"

        q10v_last = daily_returns_q10[-1] if daily_returns_q10 else 0.0
        q90v_last = daily_returns_q90[-1] if daily_returns_q90 else 0.0

        return {
            "predicted_return_pct": round(pred_return, 2),
            "direction": direction,
            "prediction_length": prediction_length,
            "all_predictions": daily_returns_q50,
            "daily_prices": daily_prices_q50,
            "lower_path": daily_returns_q10,
            "upper_path": daily_returns_q90,
            "uncertainty_range_pct": round(q90v_last - q10v_last, 1),
            "lower_10pct": round(q10v_last, 2),
            "upper_90pct": round(q90v_last, 2),
            "features_used": ["Close", "Volume", "RSI", "ATR"],
            "model": "Chronos-2 (multivariate)",
            "device_used": device_map
        }

    except Exception as e:
        return {"error": str(e)[:150], "direction": "Neutral"}