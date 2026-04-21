import time
import pandas as pd
import requests
import hmac
import hashlib

from config import *
from performance import PerformanceTracker
from trade_logger import log_trade, read_trades


class Bot:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        self.tracker = PerformanceTracker()

        # ---------------- BALANCE ----------------
        # FIX: no fake balance
        self.balance = self.tracker.get_initial_balance() if test_mode else 0.0

        self.trade_history = read_trades()
        self.is_running = False
        self.current_signal = "HOLD"

        # ---------------- MARKETS ----------------
        self.STABLE_MARKETS = ["BTCUSDT", "ETHUSDT"]

        # ---------------- RISK ----------------
        self.BASE_RISK = 0.02
        self.cooldown = 20
        self.last_trade_time = 0

        # ---------------- POSITIONS (FIXED) ----------------
        self.positions = {}  # {symbol: {"side": BUY/SELL, "entry": price}}

        # ---------------- HEARTBEAT ----------------
        self.last_heartbeat = time.time()

    # ---------------- SIGNATURE ----------------
    def sign(self, params):
        sorted_params = dict(sorted(params.items()))
        query = "&".join([f"{k}={v}" for k, v in sorted_params.items()])

        return hmac.new(
            API_SECRET.encode(),
            query.encode(),
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

            return res.json() if res.status_code == 200 else None

        except Exception as e:
            print("Request Error:", e)
            return None

    # ---------------- BALANCE ----------------
    def get_balance(self):
        data = self.send_request("GET", "/v5/account/wallet-balance", {
            "accountType": "UNIFIED"
        })

        try:
            coins = data["result"]["list"][0]["coin"]
            for c in coins:
                if c["coin"] == "USDT":
                    self.balance = float(c["walletBalance"])
                    return self.balance
        except:
            pass

        return self.balance

    # ---------------- MARKET DATA ----------------
    def fetch_klines(self, symbol, limit=50):
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

            df = pd.DataFrame(data["result"]["list"])
            df = df.iloc[::-1]

            df.columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].astype(float)

            return df

        except:
            return None

    # ---------------- INDICATORS ----------------
    def indicators(self, df):
        df["ema9"] = df["close"].ewm(span=9).mean()
        df["ema21"] = df["close"].ewm(span=21).mean()
        return df

    # ---------------- STRONGER SIGNAL ----------------
    def signal(self, df):
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # confirmation crossover
        bullish = latest["ema9"] > latest["ema21"] and prev["ema9"] <= prev["ema21"]
        bearish = latest["ema9"] < latest["ema21"] and prev["ema9"] >= prev["ema21"]

        if bullish:
            return "BUY"
        if bearish:
            return "SELL"

        return "HOLD"

    # ---------------- RISK ----------------
    def trade_size(self, price):
        risk = self.balance * self.BASE_RISK
        qty = risk / price
        return round(max(qty, 0.001), 6)

    # ---------------- EXIT STRATEGY ----------------
    def check_exit(self, symbol, price, ema9, ema21):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        entry = pos["entry"]
        side = pos["side"]

        # TP / SL
        tp = entry * 1.01
        sl = entry * 0.995

        exit_trade = False

        if side == "BUY":
            if price >= tp or price <= sl or ema9 < ema21:
                exit_trade = True

        if side == "SELL":
            if price <= entry * 0.99 or price >= entry * 1.005 or ema9 > ema21:
                exit_trade = True

        if exit_trade:
            close_side = "Sell" if side == "BUY" else "Buy"

            self.place_order(close_side, self.trade_size(price), symbol)

            log_trade({
                "symbol": symbol,
                "type": "EXIT",
                "side": close_side,
                "price": price,
                "balance": self.balance,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })

            del self.positions[symbol]

    # ---------------- ORDER ----------------
    def place_order(self, side, qty, symbol):
        res = self.send_request("POST", "/v5/order/create", {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty)
        })

        if not res or res.get("retCode") != 0:
            print("ORDER FAILED:", res)
            return None

        print("ORDER EXECUTED:", side, symbol, qty)
        return res

    # ---------------- PROCESS MARKET ----------------
    def process(self, symbol):
        df = self.fetch_klines(symbol)
        if df is None or len(df) < 30:
            return

        df = self.indicators(df)

        price = df.iloc[-1]["close"]
        ema9 = df.iloc[-1]["ema9"]
        ema21 = df.iloc[-1]["ema21"]

        signal = self.signal(df)
        self.current_signal = signal

        print(f"{symbol} | {price} | {signal}")

        # EXIT FIRST
        self.check_exit(symbol, price, ema9, ema21)

        # cooldown
        if time.time() - self.last_trade_time < self.cooldown:
            return

        # entry logic
        if signal in ["BUY", "SELL"] and symbol not in self.positions:

            qty = self.trade_size(price)
            side = "Buy" if signal == "BUY" else "Sell"

            res = self.place_order(side, qty, symbol)

            if res:
                self.positions[symbol] = {
                    "side": signal,
                    "entry": price
                }

                log_trade({
                    "symbol": symbol,
                    "type": "ENTRY",
                    "side": side,
                    "price": price,
                    "balance": self.balance,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                })

                self.last_trade_time = time.time()

    # ---------------- LOOP ----------------
    def start(self):
        self.is_running = True
        print("BOT STARTED 🚀")

        while self.is_running:
            self.get_balance()

            print(f"BALANCE: {self.balance}")

            for m in self.STABLE_MARKETS:
                self.process(m)

            # HEARTBEAT FIX
            self.last_heartbeat = time.time()
            print("HEARTBEAT ✔ BOT ALIVE")

            time.sleep(10)

    def stop(self):
        self.is_running = False
        print("BOT STOPPED 🛑")
