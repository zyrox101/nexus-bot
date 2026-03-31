import json
from datetime import datetime

def log_trade(trade):
    trade['timestamp'] = datetime.utcnow().isoformat()
    try:
        with open("trade_history.json", "a") as f:
            f.write(json.dumps(trade) + "\n")
    except Exception as e:
        print(f"Error logging trade: {e}")

def read_trades():
    trades = []
    try:
        with open("trade_history.json", "r") as f:
            for line in f:
                trades.append(json.loads(line.strip()))
    except FileNotFoundError:
        pass
    return trades
