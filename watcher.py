import os
import sqlite3
import pandas as pd
from datetime import datetime
from config import *
from strategy import fetch_klines, calculate_indicators, generate_signal

DB_FILE = "market_data.db"

def init_db():
    """Create database table if it doesn't exist"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS klines (
            timestamp INTEGER PRIMARY KEY,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            ema9 REAL,
            ema21 REAL,
            rsi REAL,
            signal TEXT
        )
    ''')
    conn.close()

def store_latest_data(df):
    """Store the latest candle data along with indicators and signal"""
    if df is None or df.empty:
        print("No data fetched")
        return

    latest = df.iloc[-1]
    sig = generate_signal(df)

    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT OR REPLACE INTO klines VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            int(latest['timestamp']),
            latest['open'],
            latest['high'],
            latest['low'],
            latest['close'],
            latest['volume'],
            latest.get('ema9', None),
            latest.get('ema21', None),
            latest.get('rsi', None),
            sig
        )
    )
    conn.commit()
    conn.close()

    print(f"✅ Stored candle at {datetime.now()} with signal: {sig}")

def main():
    init_db()
    print("Fetching latest kline...")

    try:
        df = fetch_klines(limit=50)  # get enough candles for EMA/RSI
        if df.empty:
            print("API returned no data")
            return

        df = calculate_indicators(df)
        store_latest_data(df)

    except Exception as e:
        print("Error occurred:", e)

if __name__ == "__main__":
    main()
