import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import statsmodels.api as sm
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

# ==================== CHRONOS-2 (MULTIVARIATE) ====================
def get_chronos_forecast(ticker: str, prediction_length: int = 5, use_covariates: bool = True):
    """
    Chronos-2 forecast with covariates (Volume + RSI + ATR).
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

        context_df = df[['Close', 'Volume', 'rsi', 'atr']].tail(120)
        last_price = float(context_df['Close'].iloc[-1])
        context = context_df.values.tolist()

        forecast = pipeline.predict(
            context=context,
            prediction_length=prediction_length,
            quantile_levels=[0.1, 0.5, 0.9]
        )

        q10_arr = np.atleast_1d(forecast[0].cpu().numpy())
        q50_arr = np.atleast_1d(forecast[1].cpu().numpy())
        q90_arr = np.atleast_1d(forecast[2].cpu().numpy())

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

# ==================== LSTM (keep existing) ====================
class LSTMForecaster(nn.Module):
    def __init__(self, input_size: int = 1, hidden_size: int = 128, num_layers: int = 2, output_size: int = 1, dropout: float = 0.2):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, output_size)
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])

def get_lstm_forecast(ticker: str, seq_len: int = 40, epochs: int = 80, lr: float = 0.001, batch_size: int = 64, prediction_length: int = 5):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    stock = yf.Ticker(ticker)
    try:
        hist = stock.history(period="5y")
        if len(hist) < 100: return {"predicted_return_pct": 0.5, "direction": "Neutral"}
        closes = hist['Close'].dropna()
        returns = closes.pct_change().dropna().values.astype(np.float32)
        if len(returns) <= seq_len: seq_len = max(5, len(returns) // 3)
        X_list, y_list = [], []
        for i in range(len(returns) - seq_len):
            X_list.append(returns[i:i + seq_len])
            y_list.append(returns[i + seq_len])
        X = torch.tensor(np.array(X_list), dtype=torch.float32).unsqueeze(-1)
        y = torch.tensor(np.array(y_list), dtype=torch.float32).unsqueeze(-1)
        train_size = int(len(X) * 0.9)
        X_train, y_train = X[:train_size], y[:train_size]
        model = LSTMForecaster(hidden_size=128, num_layers=2).to(device)
        criterion = nn.MSELoss()
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
        dataset = TensorDataset(X_train, y_train)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)
        model.train()
        for epoch in range(epochs):
            for xb, yb in loader:
                xb, yb = xb.to(device), yb.to(device)
                pred = model(xb)
                loss = criterion(pred, yb)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        model.eval()
        predictions = []
        current_seq = torch.tensor(returns[-seq_len:], dtype=torch.float32).unsqueeze(0).unsqueeze(-1).to(device)
        last_return = float(returns[-1])
        for step in range(prediction_length):
            with torch.no_grad():
                next_pred = model(current_seq).item()
                next_pred = max(min(next_pred, 0.06), -0.06)
                decay = 0.85 ** step
                next_pred = next_pred * decay + last_return * (1 - decay) * 0.3
                predictions.append(next_pred)
            current_seq = torch.cat([current_seq[:, 1:, :], torch.tensor([[next_pred]], dtype=torch.float32).unsqueeze(-1).to(device)], dim=1)
        final_pred = sum(predictions)
        direction = "Bullish 📈" if final_pred > 0.01 else "Bearish 📉" if final_pred < -0.01 else "Neutral ➕"
        return {"predicted_return_pct": round(final_pred * 100, 2), "direction": direction, "prediction_length": prediction_length, "all_predictions": [round(p * 100, 2) for p in predictions], "device_used": device, "model": f"LSTM ({prediction_length}d)"}
    except Exception as e: return {"predicted_return_pct": 0.0, "direction": "Neutral", "error": str(e)[:100]}