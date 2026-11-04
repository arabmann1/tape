"""Technical indicators: pure functions over pandas Series, no I/O.

Definitions follow the textbook versions (EMAs seeded with a simple average,
Wilder smoothing for RSI and ATR, population standard deviation for Bollinger
Bands) so the numbers match what most charting platforms show.
"""

import numpy as np
import pandas as pd


def _seeded_smoothing(values: np.ndarray, n: int, alpha: float) -> np.ndarray:
    """Exponential smoothing seeded with the simple mean of the first n values.
    alpha = 2/(n+1) gives a standard EMA; alpha = 1/n gives Wilder's smoothing."""
    out = np.full(len(values), np.nan)
    if len(values) < n:
        return out
    out[n - 1] = values[:n].mean()
    for i in range(n, len(values)):
        out[i] = out[i - 1] + alpha * (values[i] - out[i - 1])
    return out


def _smooth(s: pd.Series, n: int, alpha: float) -> pd.Series:
    valid = s.dropna().astype(float)
    result = pd.Series(_seeded_smoothing(valid.to_numpy(), n, alpha), index=valid.index)
    return result.reindex(s.index)


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return _smooth(s, n, 2 / (n + 1))


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Relative Strength Index, 0-100: average gain vs average loss over n bars."""
    delta = close.diff()
    gain = _smooth(delta.clip(lower=0), n, 1 / n)
    loss = _smooth((-delta).clip(lower=0), n, 1 / n)
    out = 100 - 100 / (1 + gain / loss)
    out = out.mask((loss == 0) & (gain > 0), 100.0)
    return out.mask((loss == 0) & (gain == 0), 50.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """Average True Range: the typical size of a day's move, gaps included."""
    prev = close.shift(1)
    true_range = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return _smooth(true_range, n, 1 / n)


def last_cross(fast: pd.Series, slow: pd.Series) -> dict | None:
    """Most recent date `fast` crossed `slow`, and which way."""
    diff = (fast - slow).dropna()
    sign = np.sign(diff)
    sign = sign[sign != 0]
    flips = sign.ne(sign.shift()) & sign.shift().notna()
    if not flips.any():
        return None
    when = flips[flips].index[-1]
    return {"date": when, "direction": "up" if sign[when] > 0 else "down"}


def key_levels(df: pd.DataFrame, lookback: int = 126, wing: int = 5,
               tolerance: float = 0.015, per_side: int = 3) -> list[dict]:
    """Support and resistance from swing points over the last `lookback` bars.

    A swing high is the highest high within `wing` bars on either side (a swing
    low, the lowest low). Swings within `tolerance` of each other merge into one
    level; the more touches, the more traders are likely watching it."""
    recent = df.tail(lookback)
    if len(recent) < wing * 2 + 1:
        return []
    highs, lows, dates = recent["high"].to_numpy(), recent["low"].to_numpy(), recent.index
    points = []
    for i in range(wing, len(recent) - wing):
        if highs[i] == highs[i - wing:i + wing + 1].max():
            points.append((float(highs[i]), dates[i]))
        if lows[i] == lows[i - wing:i + wing + 1].min():
            points.append((float(lows[i]), dates[i]))
    points.sort(key=lambda p: p[0])

    clusters: list[dict] = []
    for price, date in points:
        if clusters and (price - clusters[-1]["anchor"]) / clusters[-1]["anchor"] <= tolerance:
            clusters[-1]["prices"].append(price)
            clusters[-1]["dates"].append(date)
        else:
            clusters.append({"anchor": price, "prices": [price], "dates": [date]})

    last = float(df["close"].iloc[-1])
    levels = [{
        "price": round(float(np.mean(c["prices"])), 2),
        "touches": len(c["prices"]),
        "last_touch": max(c["dates"]).strftime("%Y-%m-%d"),
    } for c in clusters]
    for lv in levels:
        lv["side"] = "support" if lv["price"] < last else "resistance"
    supports = sorted((lv for lv in levels if lv["side"] == "support"), key=lambda lv: -lv["price"])
    resists = sorted((lv for lv in levels if lv["side"] == "resistance"), key=lambda lv: lv["price"])
    return supports[:per_side] + resists[:per_side]
