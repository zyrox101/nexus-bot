# watcher.py
import sqlite3
import pandas as pd
import requests
from datetime import datetime
from config import *
from performance import PerformanceTracker
from trade_logger import log_trade, read_trades
import time

DB_FILE = "market_data.db"


class Bot:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        self.tracker = PerformanceTracker()
        self.balance = 20.0
        self.current_trade = None
        self.trade_history = read_trades()
        self.is_running = False
        self.current_signal = "HOLD"

        self.STABLE_MARKETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
        self.TRADE_USDT = 2

    # ---------------- Database ----------------
    def init_db(self):
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS klines (
            timestamp INTEGER PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            ema9 REAL,
            ema21 REAL,
            rsi REAL
        )
        """)
        conn.close()

    # ---------------- Market Data ----------------
    def fetch_klines(self, symbol="BTCUSDT", limit=50):
        url = f"https://api.bybit.com/v5/market/kline?symbol={symbol}&interval=1&limit={limit}"
        r = requests.get(url).json()
        data = r["result"]["list"]
        if not data:
            return None

        df = pd.DataFrame(data)
        df = df.iloc[::-1]
        df.columns = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

        for col in ["timestamp", "open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["timestamp"] = df["timestamp"].astype(int)

        return df

    # ---------------- Indicators ----------------
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

    # ---------------- Signal ----------------
    def generate_signal(self, df):
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if self.test_mode:
            return "BUY"

        signal = "HOLD"
        # EMA crossover
        if latest["ema9"] > latest["ema21"] and prev["ema9"] <= prev["ema21"]:
            signal = "BUY"
        elif latest["ema9"] < latest["ema21"] and prev["ema9"] >= prev["ema21"]:
            signal = "SELL"

        # Trend filter
        if abs(latest["ema9"] - latest["ema21"]) < 0.1:
            return "HOLD"

        # RSI filter
        if signal == "BUY" and not (40 < latest["rsi"] < 70):
            return "HOLD"
        if signal == "SELL" and not (30 < latest["rsi"] < 60):
            return "HOLD"

        # Candle confirmation
        if signal == "BUY" and latest["close"] < latest["open"]:
            return "HOLD"
        if signal == "SELL" and latest["close"] > latest["open"]:
            return "HOLD"

        return signal

    # ---------------- TP/SL ----------------
    def calculate_tp_sl(self, price, signal):
        TP_PERCENT = 0.005  # 0.5%
        SL_PERCENT = 0.003  # 0.3%
        if signal == "BUY":
            tp = price * (1 + TP_PERCENT)
            sl = price * (1 - SL_PERCENT)
        elif signal == "SELL":
            tp = price * (1 - TP_PERCENT)
            sl = price * (1 + SL_PERCENT)
        else:
            return None, None
        return round(tp, 4), round(sl, 4)

    # ---------------- Trade Size ----------------
    def calculate_trade_size(self, price):
        qty = self.TRADE_USDT / price
        return round(qty, 6)

    # ---------------- Trade Simulation ----------------
    def simulate_trade(self, price, signal, tp, sl):
        # Open trade
        if self.current_trade is None and signal != "HOLD":
            self.current_trade = {
                "type": signal,
                "entry": price,
                "tp": tp,
                "sl": sl,
                "qty": self.calculate_trade_size(price)
            }
            print("🚀 Trade Opened:", self.current_trade)
            return

        # Manage existing trade
        if self.current_trade is not None:
            entry = self.current_trade["entry"]
            qty = self.current_trade["qty"]

            if self.current_trade["type"] == "BUY":
                if price >= self.current_trade["tp"]:
                    profit = (self.current_trade["tp"] - entry) * qty
                    self.balance += profit
                    print(f"✅ TP Hit | Profit: {round(profit,4)} | Balance: {round(self.balance,4)}")
                    self.tracker.record_trade(profit)
                    self.trade_history.append({"signal":"BUY","profit":profit,"balance":self.balance})
                    log_trade({"signal":"BUY","profit":profit,"balance":self.balance})
                    self.current_trade = None
                elif price <= self.current_trade["sl"]:
                    loss = (entry - self.current_trade["sl"]) * qty
                    self.balance -= loss
                    print(f"❌ SL Hit | Loss: {round(loss,4)} | Balance: {round(self.balance,4)}")
                    self.tracker.record_trade(-loss)
                    self.trade_history.append({"signal":"BUY","profit":-loss,"balance":self.balance})
                    log_trade({"signal":"BUY","profit":-loss,"balance":self.balance})
                    self.current_trade = None

            elif self.current_trade["type"] == "SELL":
                if price <= self.current_trade["tp"]:
                    profit = (entry - self.current_trade["tp"]) * qty
                    self.balance += profit
                    print(f"✅ TP Hit | Profit: {round(profit,4)} | Balance: {round(self.balance,4)}")
                    self.tracker.record_trade(profit)
                    self.trade_history.append({"signal":"SELL","profit":profit,"balance":self.balance})
                    log_trade({"signal":"SELL","profit":profit,"balance":self.balance})
                    self.current_trade = None
                elif price >= self.current_trade["sl"]:
                    loss = (self.current_trade["sl"] - entry) * qty
                    self.balance -= loss
                    print(f"❌ SL Hit | Loss: {round(loss,4)} | Balance: {round(self.balance,4)}")
                    self.tracker.record_trade(-loss)
                    self.trade_history.append({"signal":"SELL","profit":-loss,"balance":self.balance})
                    log_trade({"signal":"SELL","profit":-loss,"balance":self.balance})
                    self.current_trade = None

    # ---------------- Store Kline ----------------
    def store_kline(self, row):
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            """
            INSERT OR REPLACE INTO klines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["timestamp"]),
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                row["ema9"],
                row["ema21"],
                row["rsi"]
            )
        )
        conn.commit()
        conn.close()

    # ---------------- Market Processing ----------------
    def process_market(self, symbol):
        print(f"\nScanning {symbol}")
        df = self.fetch_klines(symbol)
        if df is None or df.empty:
            print("No data")
            return
        df = self.calculate_indicators(df)
        latest = df.iloc[-1]
        price = latest["close"]

        signal = self.generate_signal(df)
        tp, sl = self.calculate_tp_sl(price, signal)
        self.store_kline(latest)

        print("Time:", datetime.now())
        print("Price:", price)
        print("EMA9:", latest["ema9"])
        print("EMA21:", latest["ema21"])
        print("RSI:", latest["rsi"])
        print("Signal:", signal)
        if signal != "HOLD":
            print("TP:", tp, "SL:", sl)
            self.simulate_trade(price, signal, tp, sl)

    # ---------------- Bot Loop ----------------
    def start(self):
        self.is_running = True
        self.init_db()
        print("Bot started")
        while self.is_running:
            for market in self.STABLE_MARKETS:
                try:
                    self.process_market(market)
                except Exception as e:
                    print("Error:", e)
            time.sleep(5)

    def stop(self):
        self.is_running = False
        print("Bot stopped")

