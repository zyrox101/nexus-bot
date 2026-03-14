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

    response = requests.get(url, params=params)
    data = response.json()

    if data["retCode"] != 0:
        raise Exception(f"API Error: {data}")

    klines = data["result"]["list"]

    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close",
        "volume", "turnover"
    ])

    df = df.astype({
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "volume": float
    })

    df = df.sort_values("timestamp")
    return df


def calculate_indicators(df):
    df["ema9"] = df["close"].ewm(span=9).mean()
    df["ema21"] = df["close"].ewm(span=21).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    return df


def generate_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # LONG
    if (
        prev["ema9"] < prev["ema21"] and
        last["ema9"] > last["ema21"] and
        50 <= last["rsi"] <= 65 and
        last["close"] > last["ema9"] and
        last["close"] > last["ema21"]
    ):
        return "LONG"

    # SHORT
    if (
        prev["ema9"] > prev["ema21"] and
        last["ema9"] < last["ema21"] and
        35 <= last["rsi"] <= 50 and
        last["close"] < last["ema9"] and
        last["close"] < last["ema21"]
    ):
        return "SHORT"

    return "NONE"
