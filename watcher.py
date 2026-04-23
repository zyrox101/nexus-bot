import time
import pandas as pd
import requests
import hmac
import hashlib

from config import *
from strategy import calculate_indicators, generate_signal
from performance import PerformanceTracker
from trade_logger import log_trade, read_trades


class Bot:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        self.tracker = PerformanceTracker()

        self.balance = self.tracker.get_initial_balance() if test_mode else 0.0
        self.trade_history = read_trades()

        self.is_running = False
        self.current_signal = "HOLD"

        self.STABLE_MARKETS = ["BTCUSDT", "ETHUSDT"]

        # Risk system
        self.BASE_RISK = 0.02
        self.TAKE_PROFIT = 0.03   # +3%
        self.STOP_LOSS = 0.02     # -2%

        self.cooldown = 20
        self.last_trade_time = 0

        self.positions = {}
        self.last_heartbeat = time.time()

    # ================= SIGNATURE =================
    def sign(self, params):
        sorted_params = dict(sorted(params.items()))
        query = "&".join([f"{k}={v}" for k, v in sorted_params.items()])

        return hmac.new(
            API_SECRET.encode(),
            query.encode(),
            hashlib.sha256
        ).hexdigest()

    # ================= REQUEST =================
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
            print("❌ Request Error:", e)
            return None

    # ================= BALANCE =================
    def get_balance(self):
        if self.test_mode:
            return self.balance

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

    # ================= MARKET DATA =================
    def fetch_market_data(self, symbol, limit=200):
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

            klines = data.get("result", {}).get("list", [])
            if not klines:
                return None

            df = pd.DataFrame(klines)
            df = df.iloc[::-1]

            df.columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

            for col in ["open", "high", "low", "close"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            return df.dropna()

        except Exception as e:
            print("❌ Market Data Error:", e)
            return None

    # ================= RISK =================
    def trade_size(self, price):
        risk = self.balance * self.BASE_RISK
        qty = risk / price
        return round(max(qty, 0.001), 6)

    # ================= ORDER =================
    def place_order(self, side, qty, symbol):
        if self.test_mode:
            print(f"🧪 TEST ORDER: {side} {symbol} {qty}")
            return {"test": True}

        res = self.send_request("POST", "/v5/order/create", {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty)
        })

        if not res or res.get("retCode") != 0:
            print("❌ ORDER FAILED:", res)
            return None

        print("✅ ORDER EXECUTED:", side, symbol, qty)
        return res

    # ================= POSITION CHECK =================
    def check_exit(self, symbol, price):
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        entry = position["entry"]
        side = position["side"]

        change = (price - entry) / entry

        # SELL position logic
        if side == "SELL":
            change = -change

        # TAKE PROFIT
        if change >= self.TAKE_PROFIT:
            self.close_position(symbol, price, "TP")

        # STOP LOSS
        elif change <= -self.STOP_LOSS:
            self.close_position(symbol, price, "SL")

    # ================= CLOSE POSITION =================
    def close_position(self, symbol, price, reason):
        pos = self.positions[symbol]
        side = "Sell" if pos["side"] == "BUY" else "Buy"

        qty = self.trade_size(price)

        self.place_order(side, qty, symbol)

        profit = (price - pos["entry"])
        if pos["side"] == "SELL":
            profit = -profit

        self.tracker.record_trade(profit)

        log_trade({
            "symbol": symbol,
            "type": "EXIT",
            "reason": reason,
            "side": side,
            "price": price,
            "profit": profit,
            "balance": self.balance,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        print(f"🔴 POSITION CLOSED ({reason}): {symbol} | PnL: {profit}")

        del self.positions[symbol]
        self.last_trade_time = time.time()

    # ================= CORE LOOP =================
    def run(self):
        self.is_running = True
        print("🚀 BOT STARTED")

        while self.is_running:
            try:
                self.get_balance()

                for symbol in self.STABLE_MARKETS:

                    data = self.fetch_market_data(symbol)
                    if data is None or len(data) < 50:
                        continue

                    data = calculate_indicators(data)
                    signal = generate_signal(data)
                    self.current_signal = signal

                    price = data.iloc[-1]["close"]

                    print(f"{symbol} | {price} | {signal}")

                    # CHECK EXIT FIRST (IMPORTANT)
                    self.check_exit(symbol, price)

                    # cooldown
                    if time.time() - self.last_trade_time < self.cooldown:
                        continue

                    # ENTRY
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

                self.last_heartbeat = time.time()
                print("💓 HEARTBEAT — BOT ALIVE")

                time.sleep(10)

            except Exception as e:
                print("🔥 LOOP ERROR:", e)
                time.sleep(5)

    def stop(self):
        self.is_running = False
        print("🛑 BOT STOPPED")
