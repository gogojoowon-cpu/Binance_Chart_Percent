import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")

LIVE_TRADING = os.getenv("LIVE_TRADING", "false").lower() == "true"
USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"

SYMBOL = "BTCUSDT"
INTERVAL = "5m"

LEVERAGE = 30
MARGIN_PCT = 0.30

# --- Strategy: multi-confirmation trend-following ---
EMA_TREND = 200            # higher-TF trend filter on the same series
ST_PERIOD = 10             # Supertrend ATR period
ST_MULTIPLIER = 3.0        # Supertrend multiplier
RSI_PERIOD = 14
RSI_LONG_MIN = 50          # require RSI in this range for longs
RSI_LONG_MAX = 70
RSI_SHORT_MIN = 30
RSI_SHORT_MAX = 50
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ADX_PERIOD = 14
ADX_MIN = 20               # only trade when trend strength is high enough
VOL_AVG_LOOKBACK = 20

# --- Risk ---
STOP_LOSS_PCT = 0.005
TAKE_PROFIT_PCT = 0.010
DAILY_ROI_TARGET = 0.05
DAILY_LOSS_LIMIT = -0.10

# --- Loop / API ---
POLL_INTERVAL_SEC = 10
RECV_WINDOW_MS = 10_000
API_MAX_RETRIES = 5
KLINES_LIMIT = 300         # need >= EMA_TREND + buffer
