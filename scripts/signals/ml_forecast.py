import yfinance as yf
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

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
        if len(returns) <= seq_len + prediction_length:
            seq_len = max(5, (len(returns) - prediction_length) // 3)
        X_list, y_list = [], []
        for i in range(len(returns) - seq_len - prediction_length + 1):
            X_list.append(returns[i:i + seq_len])
            y_list.append(returns[i + seq_len : i + seq_len + prediction_length])
        if not X_list:
            return {"predicted_return_pct": 0.0, "direction": "Neutral", "error": "Insufficient data"}
        X = torch.tensor(np.array(X_list), dtype=torch.float32).unsqueeze(-1)
        y = torch.tensor(np.array(y_list), dtype=torch.float32)
        train_size = int(len(X) * 0.9)
        X_train, y_train = X[:train_size], y[:train_size]
        model = LSTMForecaster(hidden_size=128, num_layers=2, output_size=prediction_length).to(device)
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
        current_seq = torch.tensor(returns[-seq_len:], dtype=torch.float32).unsqueeze(0).unsqueeze(-1).to(device)
        with torch.no_grad():
            raw = model(current_seq).cpu().numpy().flatten()
        predictions = [float(max(min(p, 0.06), -0.06)) for p in raw]
        final_pred = sum(predictions)
        direction = "Bullish 📈" if final_pred > 0.01 else "Bearish 📉" if final_pred < -0.01 else "Neutral ➕"
        return {"predicted_return_pct": round(final_pred * 100, 2), "direction": direction, "prediction_length": prediction_length, "all_predictions": [round(p * 100, 3) for p in predictions], "device_used": device, "model": f"LSTM-DirectMH ({prediction_length}d)"}
    except Exception as e: return {"predicted_return_pct": 0.0, "direction": "Neutral", "error": str(e)[:100]}

def get_chronos_forecast(ticker: str, prediction_length: int = 5, use_covariates: bool = True):
    try:
        from chronos import Chronos2Pipeline
        import pandas_ta as ta
        device_map = "cuda" if torch.cuda.is_available() else "cpu"
        pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=device_map)
        hist = yf.Ticker(ticker).history(period="2y")
        if len(hist) < 50:
            return {"error": "Insufficient data"}
        multivariate_used = False
        features_used = ["Close"]
        last_price = float(hist['Close'].dropna().values[-1])
        if use_covariates:
            try:
                df = hist[['Close', 'Volume', 'High', 'Low']].dropna().copy()
                df['rsi'] = ta.rsi(df['Close'], length=14)
                df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
                df = df.dropna()
                if len(df) >= 60:
                    context_df = df[['Close', 'Volume', 'rsi', 'atr']].tail(120)
                    last_price = float(context_df['Close'].iloc[-1])
                    arr = context_df.values.T.astype(np.float32)
                    ctx_t = torch.from_numpy(arr).unsqueeze(0)
                    forecast = pipeline.predict(ctx_t, prediction_length=prediction_length)
                    forecast_tensor = forecast[0].cpu().numpy()
                    multivariate_used = True
                    features_used = ["Close", "Volume", "RSI", "ATR"]
            except Exception:
                pass
        if not multivariate_used:
            close = hist['Close'].dropna().values[-100:].astype(np.float32)
            last_price = float(close[-1])
            ctx_t = torch.from_numpy(close).unsqueeze(0).unsqueeze(0)
            forecast = pipeline.predict(ctx_t, prediction_length=prediction_length)
            forecast_tensor = forecast[0].cpu().numpy()
        q50 = forecast_tensor[0, 10, :] if forecast_tensor.ndim > 2 else forecast_tensor
        daily_returns = [round(float((float(p) - last_price) / last_price * 100), 3) for p in q50]
        pred_return = daily_returns[-1] if daily_returns else 0.0
        direction = "Bullish 📈" if pred_return > 1.0 else "Bearish 📉" if pred_return < -1.0 else "Neutral ➕"
        return {"predicted_return_pct": round(pred_return, 2), "direction": direction, "prediction_length": prediction_length, "all_predictions": daily_returns, "features_used": features_used, "model": "Chronos-2 (multivariate)" if multivariate_used else "Chronos-2", "device_used": device_map}
    except Exception as e:
        return {"error": str(e)[:150], "direction": "Neutral"}