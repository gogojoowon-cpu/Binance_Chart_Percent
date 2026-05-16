import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-12)
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift()
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = ((up > down) & (up > 0)).astype(float) * up
    minus_dm = ((down > up) & (down > 0)).astype(float) * down

    atr_v = atr(high, low, close, period)
    alpha = 1.0 / period
    plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_v.replace(0, 1e-12)
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_v.replace(0, 1e-12)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-12)
    return dx.ewm(alpha=alpha, adjust=False).mean()


def macd_hist(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    macd_line = ema(closes, fast) - ema(closes, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def supertrend_direction(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.Series:
    """Returns a series of +1 (bullish) / -1 (bearish)."""
    atr_v = atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper = hl2 + multiplier * atr_v
    lower = hl2 - multiplier * atr_v

    n = len(close)
    final_upper = upper.copy()
    final_lower = lower.copy()
    direction = pd.Series(index=close.index, dtype=int)

    for i in range(1, n):
        if upper.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i - 1]

        if lower.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i - 1]

    direction.iloc[0] = 1
    for i in range(1, n):
        prev_dir = direction.iloc[i - 1]
        if prev_dir == 1:
            direction.iloc[i] = -1 if close.iloc[i] < final_lower.iloc[i] else 1
        else:
            direction.iloc[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1

    return direction
