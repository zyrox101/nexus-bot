import os

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
TEST_MODE = os.environ.get("TEST_MODE", "True") == "True" 
BASE_URL = "https://api-testnet.bybit.com"
SYMBOL = "BTCUSDT"
CATEGORY = "linear"
TIMEFRAME = "15"
