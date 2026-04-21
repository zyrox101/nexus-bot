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
        self.balance = 0.0
        self.trade_history = read_trades()
        self.is_running = False
        self.current_signal = "HOLD"

        # FIXED
        self.STABLE_MARKETS = ["BTCUSDT", "ETHUSDT"]
        self.TRADE_USDT = 2

    # ---------------- SIGNATURE ----------------
    def sign(self, params):
        sorted_params = dict(sorted(params.items()))
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params.items()])

        return hmac.new(
            API_SECRET.encode(),
            param_str.encode(),
            hashlib.sha256
        ).hexdigest()

    # ---------------- SAFE REQUEST ----------------
    def send_request(self, method, endpoint, params=None):
        if params is None:
            params = {}

        url = BASE_URL + endpoint

        params["api_key"] = API_KEY
        params["timestamp"] = str(int(time.time() * 1000))
        params["recv_window"] = "5000"

        params["sign"] = self.sign(params)

        try:
            if method == "GET":
                res = requests.get(url, params=params, timeout=10)
            else:
                res = requests.post(url, json=params, timeout=10)

            print("🌐 STATUS:", res.status_code)
            print("🌐 RAW:", res.text)

            if res.status_code != 200:
                return None

            if not res.text:
                return None

            return res.json()

        except Exception as e:
            print("❌ Request Error:", e)
            return None

    # ---------------- BALANCE ----------------
    def get_balance(self):
        endpoint = "/v5/account/wallet-balance"
        params = {"accountType": "UNIFIED"}

        data = self.send_request("GET", endpoint, params)

        if not data:
            return self.balance

        try:
            coins = data["result"]["list"][0]["coin"]
            for c in coins:
                if c["coin"] == "USDT":
                    self.balance = float(c["walletBalance"])
                    return self.balance
        except Exception as e:
            print("❌ Balance error:", e)

        return self.balance

    # ---------------- PLACE ORDER (NEW) ----------------
    def place_order(self, side, qty, symbol="BTCUSDT"):
        endpoint = "/v5/order/create"

        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side,  # MUST: "Buy" or "Sell"
            "orderType": "Market",
            "qty": str(qty),
            "timeInForce": "GoodTillCancel"
        }

        response = self.send_request("POST", endpoint, params)

        print("🔎 ORDER RESPONSE:", response)

        if not response:
            print("❌ No response from API")
            return None

        if response.get("retCode") != 0:
            print("❌ ORDER FAILED:", response.get("retMsg"))
            return None

        print("✅ ORDER SUCCESS:", response["result"])
        return response["result"]

    # ---------------- KLINES ----------------
    def fetch_klines(self, symbol="BTCUSDT", limit=50):
        url = f"{BASE_URL}/v5/market/kline"

        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": "1",
            "limit": limit
        }

        try:
            r = requests.get(url, params=params, timeout=10)

            if r.status_code != 200:
                print("❌ HTTP ERROR:", r.status_code, r.text)
                return None

            data = r.json()

            if not data or data.get("retCode") != 0:
                print("❌ BYBIT ERROR:", data)
                return None

            klines = data["result"]["list"]

            df = pd.DataFrame(klines)
            df = df.iloc[::-1]

            df.columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")

            return df

        except Exception as e:
            print("❌ Klines error:", e)
            return None

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

        if abs(latest["ema9"] - latest["ema21"]) < 0.5:
            return "HOLD"

        return signal

    # ---------------- TRADE SIZE ----------------
    def calculate_trade_size(self, price):
        return round(self.TRADE_USDT / price, 6)

    # ---------------- PROCESS MARKET ----------------
    def process_market(self, symbol):
        df = self.fetch_klines(symbol)

        if df is None or df.empty:
            return

        df = self.calculate_indicators(df)
        latest = df.iloc[-1]

        price = float(latest["close"])
        signal = self.generate_signal(df)

        self.current_signal = signal

        print(f"{symbol} | Price: {price} | Signal: {signal}")

        if signal != "HOLD":
            qty = self.calculate_trade_size(price)

            print(f"🚀 EXECUTING {signal} ORDER | QTY: {qty}")

            # ⚠️ TEMPORARY FORCE REAL EXECUTION
            self.place_order("Buy" if signal == "BUY" else "Sell", qty, symbol)

    # ---------------- BOT LOOP ----------------
    def start(self):
        self.is_running = True
        print("🚀 Bot started")

        while self.is_running:
            self.get_balance()

            for market in self.STABLE_MARKETS:
                try:
                    self.process_market(market)
                except Exception as e:
                    print("❌ Error:", e)

            time.sleep(5)

    def stop(self):
        self.is_running = False
        print("🛑 Bot stopped")

if __name__ == "__main__":
    bot = Bot(test_mode=False)
    bot.start()






