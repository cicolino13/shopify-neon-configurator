"""Technical indicators used by the scalping strategy, computed with pandas only
(no external TA library) so the project has minimal dependencies.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


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


def add_indicators(
    df: pd.DataFrame,
    ema_fast: int,
    ema_slow: int,
    rsi_period: int,
    atr_period: int,
) -> pd.DataFrame:
    """Return a copy of df with ema_fast, ema_slow, rsi and atr columns added."""
    out = df.copy()
    out["ema_fast"] = ema(out["close"], ema_fast)
    out["ema_slow"] = ema(out["close"], ema_slow)
    out["rsi"] = rsi(out["close"], rsi_period)
    out["atr"] = atr(out, atr_period)
    return out
