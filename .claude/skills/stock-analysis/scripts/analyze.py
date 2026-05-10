import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from fetch_data import fetch_stock_data
from score import calculate_pillars
from montecarlo import run_monte_carlo
from report import generate_report

# TODO: Will import from decision_engine and signals in v5.0
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ticker')
    parser.add_argument('--profile', default='Balanced')
    parser.add_argument('--output', choices=['text', 'json'], default='text')
    args = parser.parse_args()

    data = fetch_stock_data(args.ticker)
    scores = calculate_pillars(data)

    volatility = data['info'].get('beta', 1.0) * 0.25
    drift = (scores['overall'] - 50) / 100 * 0.25
    mc = run_monte_carlo(data['current_price'], volatility, drift)

    if args.output == 'json':
        output = {
            "ticker": data['ticker'],
            "timestamp": datetime.now().isoformat(),
            "current_price": data['current_price'],
            "overall_score": scores['overall'],
            "recommendation": "BUY" if scores['overall'] > 70 else "HOLD",
            "confidence": round(scores['overall'] / 100, 2),
            "signals": scores,
            "monte_carlo": mc,
            "suggested_action": {
                "action": "BUY",
                "quantity": 50,
                "stop_loss": data['current_price'] * 0.85,
                "take_profit": data['current_price'] * 1.25
            }
        }
        print(json.dumps(output, indent=2))
        # Save to file
        Path('output').mkdir(exist_ok=True)
        with open(f"output/signals_{data['ticker']}.json", "w") as f:
            json.dump(output, f, indent=2)
    else:
        generate_report(data, scores, mc, args.profile)

if __name__ == "main__":
    main()