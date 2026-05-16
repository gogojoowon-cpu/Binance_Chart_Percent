from typing import Optional

import pandas as pd

from config import (
    ADX_MIN,
    ADX_PERIOD,
    EMA_TREND,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    RSI_LONG_MAX,
    RSI_LONG_MIN,
    RSI_PERIOD,
    RSI_SHORT_MAX,
    RSI_SHORT_MIN,
    ST_MULTIPLIER,
    ST_PERIOD,
    VOL_AVG_LOOKBACK,
)
from indicators import adx, ema, macd_hist, rsi, supertrend_direction


def decide(df: pd.DataFrame) -> Optional[str]:
    """Multi-confirmation: trend (EMA200) + Supertrend + RSI + MACD + ADX + Volume.

    Returns 'LONG', 'SHORT', or None.
    """
    needed = max(EMA_TREND, MACD_SLOW * 2, ST_PERIOD * 3, 60)
    if len(df) < needed:
        return None

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    trend = ema(close, EMA_TREND)
    st_dir = supertrend_direction(high, low, close, ST_PERIOD, ST_MULTIPLIER)
    rsi_v = rsi(close, RSI_PERIOD)
    mh = macd_hist(close, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    adx_v = adx(high, low, close, ADX_PERIOD)
    vol_avg = volume.rolling(VOL_AVG_LOOKBACK).mean()

    i = -1
    price = close.iloc[i]
    above_trend = price > trend.iloc[i]
    below_trend = price < trend.iloc[i]
    st_bull = st_dir.iloc[i] == 1
    st_bear = st_dir.iloc[i] == -1
    rsi_now = rsi_v.iloc[i]
    rsi_bull = RSI_LONG_MIN < rsi_now < RSI_LONG_MAX
    rsi_bear = RSI_SHORT_MIN < rsi_now < RSI_SHORT_MAX
    macd_bull = mh.iloc[i] > 0
    macd_bear = mh.iloc[i] < 0
    adx_strong = adx_v.iloc[i] > ADX_MIN
    vol_ok = volume.iloc[i] > vol_avg.iloc[i]

    if above_trend and st_bull and rsi_bull and macd_bull and adx_strong and vol_ok:
        return "LONG"
    if below_trend and st_bear and rsi_bear and macd_bear and adx_strong and vol_ok:
        return "SHORT"
    return None
