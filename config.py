import os

# =========================
# API KEYS
# =========================
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

# Safety check (IMPORTANT for Render)
if not API_KEY or not API_SECRET:
    print("WARNING: API keys are missing! Check environment variables.")

# =========================
# MODE CONTROL
# =========================
TEST_MODE = str(os.environ.get("TEST_MODE", "False")).strip().lower() in ["true", "1", "yes"]

# =========================
# BASE URL
# =========================
BASE_URL = (
    "https://api-testnet.bybit.com"
    if TEST_MODE
    else "https://api.bybit.com"
)

# =========================
# TRADING SETTINGS
# =========================
SYMBOL = os.environ.get("SYMBOL", "BTCUSDT")
CATEGORY = os.environ.get("CATEGORY", "linear")
TIMEFRAME = os.environ.get("TIMEFRAME", "15")

# =========================
# DEBUG LOG (important for Render)
# =========================
print("CONFIG LOADED:")
print("TEST_MODE:", TEST_MODE)
print("BASE_URL:", BASE_URL)
print("SYMBOL:", SYMBOL)
print("CATEGORY:", CATEGORY)
print("TIMEFRAME:", TIMEFRAME)
