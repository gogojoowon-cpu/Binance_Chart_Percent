from typing import Optional

import pandas as pd

from config import EMA_FAST, EMA_SLOW, VOLUME_LOOKBACK, VOLUME_SPIKE_MULT
from indicators import ema, is_volume_spike


def decide(df: pd.DataFrame) -> Optional[str]:
    """Return 'LONG', 'SHORT', or None based on EMA cross + volume spike."""
    if len(df) < max(EMA_SLOW, VOLUME_LOOKBACK) + 2:
        return None

    closes = df["close"].astype(float)
    volumes = df["volume"].astype(float)

    fast = ema(closes, EMA_FAST)
    slow = ema(closes, EMA_SLOW)

    if not is_volume_spike(volumes, VOLUME_LOOKBACK, VOLUME_SPIKE_MULT):
        return None

    last_close = closes.iloc[-1]
    prev_close = closes.iloc[-2]
    fast_now = fast.iloc[-1]
    slow_now = slow.iloc[-1]

    if fast_now > slow_now and last_close > prev_close:
        return "LONG"
    if fast_now < slow_now and last_close < prev_close:
        return "SHORT"
    return None
