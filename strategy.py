import requests
import pandas as pd
from config import BASE_URL, SYMBOL, CATEGORY, TIMEFRAME


def fetch_klines(limit=200):
    url = f"{BASE_URL}/v5/market/kline"

    params = {
        "category": CATEGORY,
        "symbol": SYMBOL,
        "interval": TIMEFRAME,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data.get("retCode") != 0:
            print("API Error:", data)
            return pd.DataFrame()

        klines = data["result"]["list"]

        if not klines:
            print("No kline data returned")
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover"
        ])

        df = df.astype({
            "timestamp": int,
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": float
        })

        df = df.sort_values("timestamp")
        df.reset_index(drop=True, inplace=True)

        return df

    except Exception as e:
        print("Fetch klines error:", e)
        return pd.DataFrame()


def calculate_indicators(df):
    if df is None or df.empty:
        return df

    # EMA
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    return df


def generate_signal(df):
    if df is None or len(df) < 2:
        return "HOLD"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # BUY (LONG)
    if (
        prev["ema9"] < prev["ema21"]
        and last["ema9"] > last["ema21"]
        and 45 <= last["rsi"] <= 65
    ):
        return "BUY"

    # SELL (SHORT)
    if (
        prev["ema9"] > prev["ema21"]
        and last["ema9"] < last["ema21"]
        and 35 <= last["rsi"] <= 55
    ):
        return "SELL"

    return "HOLD"
