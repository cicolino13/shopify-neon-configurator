"""A fast EMA-crossover scalping strategy with an RSI filter, meant for short
timeframes (e.g. M1) such as intraday XAU/USD scalping.

Entry logic:
  - BUY when the fast EMA crosses above the slow EMA and RSI is not already
    overbought (avoids buying into an exhausted move).
  - SELL when the fast EMA crosses below the slow EMA and RSI is not already
    oversold.

This is a simple, well-known baseline strategy for demonstration and
backtesting purposes. It is NOT a proven profitable strategy on its own —
always backtest and paper-trade before considering live use.
"""
from __future__ import annotations

import pandas as pd

from .base import Signal, Strategy


class EmaRsiScalper(Strategy):
    def __init__(
        self,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
    ) -> None:
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

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
