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
        last_return = returns[-1]  # seed with actual last return
        for step in range(prediction_length):
            with torch.no_grad():
                next_pred = model(current_seq).item()
                # Stronger stabilization for realistic paths
                next_pred = max(min(next_pred, 0.06), -0.06)          # tighter clip
                # Mean-reversion: pull toward zero as horizon increases
                decay = 0.85 ** step
                next_pred = next_pred * decay + last_return * (1 - decay) * 0.3
                predictions.append(next_pred)
            current_seq = torch.cat([current_seq[:, 1:, :], torch.tensor([[next_pred]], dtype=torch.float32).unsqueeze(-1).to(device)], dim=1)
        final_pred = sum(predictions)  # cumulative return over horizon
        direction = "Bullish 📈" if final_pred > 0.01 else "Bearish 📉" if final_pred < -0.01 else "Neutral ➕"
        return {"predicted_return_pct": round(final_pred * 100, 2), "direction": direction, "prediction_length": prediction_length, "all_predictions": [round(p * 100, 2) for p in predictions], "device_used": device, "model": f"LSTM ({prediction_length}d)"}
    except Exception as e: return {"predicted_return_pct": 0.0, "direction": "Neutral", "error": str(e)[:100]}