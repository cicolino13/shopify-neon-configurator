"""Bollinger-band mean-reversion.

Where the EMA scalper bets that a move continues, this bets the opposite:
that a stretch far from the mean snaps back. The two therefore tend to
perform well in opposite market conditions -- trending vs. ranging -- which
is precisely why it is worth testing both on your own data rather than
assuming either one works.

Entry logic (re-entry, not touch): a signal fires only once price has moved
*back inside* the band, which avoids repeatedly entering against a strong
trend that simply keeps riding the band.
  - BUY  when the previous close was below the lower band and this close is
    back above it.
  - SELL when the previous close was above the upper band and this close is
    back below it.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import bollinger
from .base import Signal, Strategy


class BollingerReversion(Strategy):
    name = "bollinger_reversion"

    def __init__(self, period: int = 20, num_std: float = 2.0) -> None:
        if period < 2:
            raise ValueError("period must be at least 2")

        self.period = period
        self.num_std = num_std

    @property
    def warmup_bars(self) -> int:
        return self.period + 1

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        mid, upper, lower = bollinger(out["close"], self.period, self.num_std)
        out["bb_mid"], out["bb_upper"], out["bb_lower"] = mid, upper, lower
        return out

    def on_candle(self, history: pd.DataFrame) -> Signal:
        if len(history) < 2:
            return Signal("HOLD", "not enough history")

        prev, curr = history.iloc[-2], history.iloc[-1]

        if pd.isna(prev["bb_lower"]) or pd.isna(curr["bb_lower"]):
            return Signal("HOLD", "bands not warmed up")

        if prev["close"] < prev["bb_lower"] and curr["close"] >= curr["bb_lower"]:
            return Signal("BUY", "close re-entered the lower band")

        if prev["close"] > prev["bb_upper"] and curr["close"] <= curr["bb_upper"]:
            return Signal("SELL", "close re-entered the upper band")

        return Signal("HOLD")
