import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def is_volume_spike(volume: pd.Series, lookback: int, mult: float) -> bool:
    if len(volume) < lookback + 1:
        return False
    recent_avg = volume.iloc[-lookback - 1 : -1].mean()
    if recent_avg <= 0:
        return False
    return volume.iloc[-1] > recent_avg * mult
