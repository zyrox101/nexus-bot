import os

# ===== API KEYS =====
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

# ===== MODE CONTROL (FIXED BOOLEAN) =====
TEST_MODE = os.environ.get("TEST_MODE", "False").lower() == "true"

# ===== BASE URL (FIXED LOGIC) =====
if TEST_MODE:
    BASE_URL = "https://api-testnet.bybit.com"
else:
    BASE_URL = "https://api.bybit.com"

# ===== TRADING SETTINGS =====
SYMBOL = "BTCUSDT"
CATEGORY = "linear"
TIMEFRAME = "15"

