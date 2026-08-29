"""Strategy interface: a strategy only decides entries. Exits (stop-loss /
take-profit) are always managed by the risk manager and broker, never by the
strategy itself, so every strategy implementation gets the same risk controls
for free.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Signal:
    action: Action
    reason: str = ""


class Strategy(ABC):
    @abstractmethod
    def on_candle(self, history: pd.DataFrame) -> Signal:
        """Given all candles up to and including the current (closed) one,
        with indicator columns already attached, return a trading signal.
        Only called while the bot is flat (no open position).
        """
        raise NotImplementedError
