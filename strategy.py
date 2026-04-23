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

        data = response.json() if response.text else None

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

        # safe numeric conversion
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")

        df = df.dropna().sort_values("timestamp").reset_index(drop=True)

        return df

    except Exception as e:
        print("Fetch klines error:", e)
        return pd.DataFrame()


# =========================
# INDICATORS (IMPROVED)
# =========================
def calculate_indicators(df):
    if df is None or df.empty:
        return df

    # EMA trend
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

    # RSI (safer version)
    delta = df["close"].diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, np.nan)

    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # Volatility filter (ATR-style simple proxy)
    df["volatility"] = (df["high"] - df["low"]).rolling(14).mean()

    df = df.dropna()

    return df


# =========================
# SIGNAL GENERATION (IMPROVED + FILTERED)
# =========================
def generate_signal(df):
    if df is None or len(df) < 50:
        return "HOLD"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # safety checks
    required = ["ema9", "ema21", "rsi", "volatility"]
    if any(pd.isna(last[r]) for r in required):
        return "HOLD"

    # avoid sideways / low quality market
    if last["volatility"] < 0.0005:
        return "HOLD"

    # TREND CONFIRMATION
    bullish_trend = last["ema9"] > last["ema21"]
    bearish_trend = last["ema9"] < last["ema21"]

    # MOMENTUM SHIFT
    cross_up = prev["ema9"] < prev["ema21"] and last["ema9"] > last["ema21"]
    cross_down = prev["ema9"] > prev["ema21"] and last["ema9"] < last["ema21"]

    # RSI filters (tightened to reduce noise)
    strong_buy = 45 <= last["rsi"] <= 60
    strong_sell = 40 <= last["rsi"] <= 55

    # FINAL SIGNAL LOGIC
    if cross_up and bullish_trend and strong_buy:
        return "BUY"

    if cross_down and bearish_trend and strong_sell:
        return "SELL"

    return "HOLD"
