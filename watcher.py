import sqlite3
import pandas as pd
import requests
import time
import hmac
import hashlib

from config import *
from performance import PerformanceTracker
from trade_logger import log_trade, read_trades

DB_FILE = "market_data.db"


class Bot:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        self.tracker = PerformanceTracker()

        # 🔥 FIX: start balance from tracker or default
        self.balance = 20.0 if test_mode else 0.0

        self.trade_history = read_trades()
        self.is_running = False
        self.current_signal = "HOLD"

        self.STABLE_MARKETS = ["BTCUSDT", "ETHUSDT"]

        # FIX: dynamic risk instead of fixed
        self.BASE_RISK = 0.02  # 2% per trade max
        self.last_trade_time = 0
        self.cooldown = 20  # seconds between trades

        self.position = {}  # track open positions per symbol

    # ---------------- SIGNATURE ----------------
    def sign(self, params):
        sorted_params = dict(sorted(params.items()))
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params.items()])

        return hmac.new(
            API_SECRET.encode(),
            param_str.encode(),
            hashlib.sha256
        ).hexdigest()

    # ---------------- REQUEST ----------------
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

            if res.status_code != 200:
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

        try:
            coins = data["result"]["list"][0]["coin"]
            for c in coins:
                if c["coin"] == "USDT":
                    self.balance = float(c["walletBalance"])
                    return self.balance
        except:
            pass

        return self.balance

    # ---------------- ORDER ----------------
    def place_order(self, side, qty, symbol="BTCUSDT"):
        endpoint = "/v5/order/create"

        params = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty)
        }

        response = self.send_request("POST", endpoint, params)

        if not response or response.get("retCode") != 0:
            print("❌ ORDER FAILED:", response)
            return None

        print("✅ ORDER EXECUTED:", side, qty, symbol)
        return response["result"]

    # ---------------- MARKET DATA ----------------
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
            data = r.json()

            klines = data["result"]["list"]
            df = pd.DataFrame(klines)
            df = df.iloc[::-1]

            df.columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].astype(float)

            return df

        except:
            return None

    # ---------------- INDICATORS ----------------
    def calculate_indicators(self, df):
        df["ema9"] = df["close"].ewm(span=9).mean()
        df["ema21"] = df["close"].ewm(span=21).mean()

        return df

    # ---------------- SIGNAL (IMPROVED) ----------------
    def generate_signal(self, df):
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        ema9 = latest["ema9"]
        ema21 = latest["ema21"]

        # FIX: stronger trend confirmation
        if ema9 > ema21 and latest["close"] > ema9:
            return "BUY"

        if ema9 < ema21 and latest["close"] < ema9:
            return "SELL"

        return "HOLD"

    # ---------------- RISK CONTROL ----------------
    def calculate_trade_size(self, price):
        risk_amount = self.balance * self.BASE_RISK

        qty = risk_amount / price

        return round(max(qty, 0.001), 6)

    # ---------------- MARKET PROCESS ----------------
    def process_market(self, symbol):
        df = self.fetch_klines(symbol)
        if df is None or len(df) < 30:
            return

        df = self.calculate_indicators(df)

        price = float(df.iloc[-1]["close"])
        signal = self.generate_signal(df)

        self.current_signal = signal

        print(f"{symbol} | Price: {price} | Signal: {signal}")

        # 🔥 COOLDOWN FIX
        if time.time() - self.last_trade_time < self.cooldown:
            return

        # 🔥 PREVENT SAME POSITION STACKING
        if symbol in self.position and self.position[symbol] == signal:
            return

        if signal in ["BUY", "SELL"]:
            qty = self.calculate_trade_size(price)

            side = "Buy" if signal == "BUY" else "Sell"

            result = self.place_order(side, qty, symbol)

            if result:
                self.position[symbol] = signal
                self.last_trade_time = time.time()

    # ---------------- LOOP ----------------
    def start(self):
        self.is_running = True
        print("🚀 Bot started")

        while self.is_running:
            self.get_balance()

            print(f"💰 Balance: {self.balance}")

            for market in self.STABLE_MARKETS:
                self.process_market(market)

            time.sleep(10)  # FIX: reduced spam trading frequency

    def stop(self):
        self.is_running = False
        print("🛑 Bot stopped")


if __name__ == "__main__":
    bot = Bot(test_mode=False)
    bot.start()
