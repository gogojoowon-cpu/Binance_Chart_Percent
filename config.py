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
RSI_LONG_MIN = 48          # require RSI in this range for longs
RSI_LONG_MAX = 72
RSI_SHORT_MIN = 28
RSI_SHORT_MAX = 52
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ADX_PERIOD = 14
ADX_MIN = 18               # only trade when trend strength is high enough
VOL_AVG_LOOKBACK = 20

# --- Risk: ATR-based dynamic SL/TP (adapts to volatility) ---
ATR_PERIOD = 14
ATR_SL_MULT = 1.5          # SL distance = 1.5 * ATR
ATR_TP_MULT = 3.0          # TP distance = 3.0 * ATR  (R:R 1:2)
MIN_SL_PCT = 0.003         # floor on SL distance (0.3% of price) — avoid noise stops
MAX_SL_PCT = 0.008         # cap on SL distance (0.8%) — avoid catastrophic single trade

DAILY_ROI_TARGET = 0.05
DAILY_LOSS_LIMIT = -0.10

# --- Loop / API ---
POLL_INTERVAL_SEC = 10
RECV_WINDOW_MS = 10_000
API_MAX_RETRIES = 5
KLINES_LIMIT = 300         # need >= EMA_TREND + buffer
