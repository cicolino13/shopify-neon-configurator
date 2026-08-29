"""A fast EMA-crossover scalping strategy with an RSI filter, meant for short
timeframes (e.g. M1) such as intraday XAU/USD scalping.

Entry logic:
  - BUY when the fast EMA crosses above the slow EMA and RSI is not already
    overbought (avoids buying into an exhausted move).
  - SELL when the fast EMA crosses below the slow EMA and RSI is not already
    oversold.

This is a simple, well-known baseline strategy for demonstration and
backtesting purposes. It is NOT a proven profitable strategy on its own --
crossover systems on very short timeframes are especially vulnerable to
being eaten alive by spread, so always backtest it with a realistic cost
model before drawing any conclusions.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import ema, rsi
from .base import Signal, Strategy


class EmaRsiScalper(Strategy):
    name = "ema_rsi_scalper"

    def __init__(
        self,
        ema_fast: int = 9,
        ema_slow: int = 21,
        rsi_period: int = 14,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
    ) -> None:
        if ema_fast >= ema_slow:
            raise ValueError("ema_fast must be shorter than ema_slow")

        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    @property
    def warmup_bars(self) -> int:
        return max(self.ema_slow, self.rsi_period) + 1

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["ema_fast"] = ema(out["close"], self.ema_fast)
        out["ema_slow"] = ema(out["close"], self.ema_slow)
        out["rsi"] = rsi(out["close"], self.rsi_period)
        return out

    def on_candle(self, history: pd.DataFrame) -> Signal:
        if len(history) < 2:
            return Signal("HOLD", "not enough history")

        prev, curr = history.iloc[-2], history.iloc[-1]

        crossed_up = prev["ema_fast"] <= prev["ema_slow"] and curr["ema_fast"] > curr["ema_slow"]
        crossed_down = prev["ema_fast"] >= prev["ema_slow"] and curr["ema_fast"] < curr["ema_slow"]

        if crossed_up and curr["rsi"] < self.rsi_overbought:
            return Signal("BUY", "ema_fast crossed above ema_slow")

        if crossed_down and curr["rsi"] > self.rsi_oversold:
            return Signal("SELL", "ema_fast crossed below ema_slow")

        return Signal("HOLD")
