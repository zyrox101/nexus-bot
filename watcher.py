# watcher.py
import sqlite3
import pandas as pd
import requests
from datetime import datetime
from config import *
from performance import PerformanceTracker
from trade_logger import log_trade, read_trades
import time
import hmac
import hashlib

DB_FILE = "market_data.db"


class Bot:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        self.tracker = PerformanceTracker()
        self.balance = 0.0  # REAL balance
        self.trade_history = read_trades()
        self.is_running = False
        self.current_signal = "HOLD"

        self.STABLE_MARKETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
        self.TRADE_USDT = 2

    # ---------------- SIGNED REQUEST ----------------
    def sign_request(self, params):
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            API_SECRET.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def send_request(self, method, endpoint, params=None):
        if params is None:
            params = {}

        params["api_key"] = API_KEY
        params["timestamp"] = int(time.time() * 1000)

        params["sign"] = self.sign_request(params)

        url = BASE_URL + endpoint

        if method == "GET":
            return requests.get(url, params=params).json()
        else:
            return requests.post(url, json=params).json()

    # ---------------- GET BALANCE ----------------
    def get_balance(self):
        endpoint = "/v5/account/wallet-balance"
        params = {"accountType": "UNIFIED"}

        res = self.send_request("GET", endpoint, params)

        try:
            coins = res["result"]["list"][0]["coin"]
            for coin in coins:
                if coin["coin"] == "USDT":
                    self.balance = float(coin["walletBalance"])
                    return self.balance
        except Exception as e:
            print("Balance fetch error:", e)

        return self.balance

    # ---------------- PLACE ORDER ----------------
    def place_order(self, symbol, side, qty):
        endpoint = "/v5/order/create"

        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
            "timeInForce": "GoodTillCancel"
        }

        res = self.send_request("POST", endpoint, params)
        print("Order response:", res)

        return res

    # ---------------- MARKET DATA ----------------
    def fetch_klines(self, symbol="BTCUSDT", limit=50):
        url = f"{BASE_URL}/v5/market/kline?symbol={symbol}&interval=1&limit={limit}&category=linear"
        r = requests.get(url).json()

        data = r["result"]["list"]
        if not data:
            return None

        df = pd.DataFrame(data)
        df = df.iloc[::-1]

        df.columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        df["timestamp"] = df["timestamp"].astype(int)

        return df

    # ---------------- INDICATORS ----------------
    def calculate_indicators(self, df):
        df["ema9"] = df["close"].ewm(span=9).mean()
        df["ema21"] = df["close"].ewm(span=21).mean()

        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()

        rs = avg_gain / avg_loss
        df["rsi"] = 100 - (100 / (1 + rs))

        return df

    # ---------------- SIGNAL ----------------
    def generate_signal(self, df):
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        signal = "HOLD"

        if latest["ema9"] > latest["ema21"] and prev["ema9"] <= prev["ema21"]:
            signal = "BUY"
        elif latest["ema9"] < latest["ema21"] and prev["ema9"] >= prev["ema21"]:
            signal = "SELL"

        if abs(latest["ema9"] - latest["ema21"]) < 0.1:
            return "HOLD"

        if signal == "BUY" and not (40 < latest["rsi"] < 70):
            return "HOLD"

        if signal == "SELL" and not (30 < latest["rsi"] < 60):
            return "HOLD"

        if signal == "BUY" and latest["close"] < latest["open"]:
            return "HOLD"

        if signal == "SELL" and latest["close"] > latest["open"]:
            return "HOLD"

        return signal

    # ---------------- TRADE SIZE ----------------
    def calculate_trade_size(self, price):
        return round(self.TRADE_USDT / price, 6)

    # ---------------- EXECUTE REAL TRADE ----------------
    def execute_trade(self, symbol, price, signal):
        qty = self.calculate_trade_size(price)

        side = "Buy" if signal == "BUY" else "Sell"

        order = self.place_order(symbol, side, qty)

        if order.get("retCode") == 0:
            print("✅ Order placed:", signal, symbol)

            self.trade_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "pair": symbol,
                "signal": signal,
                "entry": price,
                "exit": None,
                "profit": 0
            })

            log_trade(self.trade_history[-1])
        else:
            print("❌ Order failed:", order)

    # ---------------- PROCESS MARKET ----------------
    def process_market(self, symbol):
        df = self.fetch_klines(symbol)

        if df is None or df.empty:
            return

        df = self.calculate_indicators(df)
        latest = df.iloc[-1]

        price = latest["close"]
        signal = self.generate_signal(df)

        self.current_signal = signal

        print(f"{symbol} | Price: {price} | Signal: {signal}")

        if signal != "HOLD":
            self.execute_trade(symbol, price, signal)

    # ---------------- BOT LOOP ----------------
    def start(self):
        self.is_running = True
        print("Bot started")

        while self.is_running:
            self.get_balance()  # REAL BALANCE

            for market in self.STABLE_MARKETS:
                try:
                    self.process_market(market)
                except Exception as e:
                    print("Error:", e)

            time.sleep(5)

    def stop(self):
        self.is_running = False
        print("Bot stopped")

