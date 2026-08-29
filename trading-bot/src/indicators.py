"""Technical indicators, computed with pandas only (no external TA library)
so the project has minimal dependencies.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))
    # avg_loss == 0 and avg_gain > 0 -> rs is +inf -> RSI should be 100
    result = result.replace([np.inf, -np.inf], 100.0)
    # avg_loss == 0 and avg_gain == 0 (no movement yet, or the warm-up period) -> neutral
    return result.fillna(50.0)


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(alpha=1 / period, adjust=False).mean()


def bollinger(series: pd.Series, period: int, num_std: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (middle, upper, lower) Bollinger bands."""
    mid = sma(series, period)
    # ddof=0: population std, the convention used for Bollinger bands
    std = series.rolling(period).std(ddof=0)
    return mid, mid + num_std * std, mid - num_std * std


def add_atr(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Attach the ATR column the risk manager needs for stop/target sizing.
    Applied by the engine for every strategy.
    """
    out = df.copy()
    out["atr"] = atr(out, period)
    return out
