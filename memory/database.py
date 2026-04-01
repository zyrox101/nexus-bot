import sqlite3
from pathlib import Path

# Path to the database file
DB_PATH = Path(__file__).parent.parent / "market_data.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
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
    ''')

    conn.commit()
    conn.close()


def save_kline(kline):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO klines (
            timestamp, open, high, low, close, volume, ema9, ema21, rsi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        kline["timestamp"],
        kline["open"],
        kline["high"],
        kline["low"],
        kline["close"],
        kline["volume"],
        kline["ema9"],
        kline["ema21"],
        kline["rsi"]
    ))

    conn.commit()
    conn.close()


def fetch_klines():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM klines ORDER BY timestamp DESC")
    rows = cursor.fetchall()

    conn.close()
    return rows


# Initialize database
init_db()
