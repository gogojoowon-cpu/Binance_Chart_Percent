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

EMA_FAST = 9
EMA_SLOW = 21
VOLUME_LOOKBACK = 20
VOLUME_SPIKE_MULT = 1.8

STOP_LOSS_PCT = 0.005
TAKE_PROFIT_PCT = 0.010

DAILY_ROI_TARGET = 0.05
DAILY_LOSS_LIMIT = -0.10

POLL_INTERVAL_SEC = 10
