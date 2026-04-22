import requests
import pandas as pd
import numpy as np
from config import BASE_URL, SYMBOL, CATEGORY, TIMEFRAME


# =========================
# FETCH MARKET DATA
# =========================
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

        try:
            data = response.json()
        except Exception as e:
            print("JSON decode error:", e)
            return pd.DataFrame()

        if not isinstance(data, dict):
            print("Invalid API response")
            return pd.DataFrame()

        if data.get("retCode") != 0:
            print("API Error:", data)
            return pd.DataFrame()

        klines = data.get("result", {}).get("list", [])
        if not klines:
            print("No kline data")
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

        # convert safely
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")

        df = df.dropna()
        df = df.sort_values("timestamp").reset_index(drop=True)

        return df

    except Exception as e:
        print("Fetch klines error:", e)
        return pd.DataFrame()


# =========================
# INDICATORS ONLY
# =========================
def calculate_indicators(df):
    if df is None or df.empty:
        return df

    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    # prevent division error
    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["rsi"] = 100 - (100 / (1 + rs))

    # IMPORTANT: do NOT fill RSI with 0 (it breaks logic)
    df = df.dropna()

    return df


# =========================
# SIGNAL GENERATION ONLY
# =========================
def generate_signal(df):
    if df is None or len(df) < 30:
        return "HOLD"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # safety check
    if (
        pd.isna(last["ema9"]) or pd.isna(last["ema21"]) or pd.isna(last["rsi"])
    ):
        return "HOLD"

    # BUY signal
    bullish = (
        prev["ema9"] < prev["ema21"]
        and last["ema9"] > last["ema21"]
        and 45 <= last["rsi"] <= 65
    )

    # SELL signal
    bearish = (
        prev["ema9"] > prev["ema21"]
        and last["ema9"] < last["ema21"]
        and 35 <= last["rsi"] <= 55
    )

    if bullish:
        return "BUY"

    if bearish:
        return "SELL"

    return "HOLD"

