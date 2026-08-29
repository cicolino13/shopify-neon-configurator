"""Strategy interface.

A strategy only decides *entries*. Exits (stop-loss / take-profit) are always
managed by the risk manager and broker, never by the strategy itself, so
every strategy implementation gets the same risk controls for free.

Each strategy also declares the indicator columns it needs (`prepare`) and
how many bars it must see before its signals are meaningful (`warmup_bars`),
so the engine can support any strategy without knowing its internals.
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
    #: Human-readable name used by the registry and CLI.
    name: str = "strategy"

    @property
    @abstractmethod
    def warmup_bars(self) -> int:
        """Bars needed before `on_candle` produces meaningful signals."""
        raise NotImplementedError

    @abstractmethod
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of df with this strategy's indicator columns added.
        Called once by the engine before the bar loop.
        """
        raise NotImplementedError

    @abstractmethod
    def on_candle(self, history: pd.DataFrame) -> Signal:
        """Given all candles up to and including the current (closed) one,
        with indicator columns already attached, return a trading signal.
        Only called while the bot is flat (no open position).
        """
        raise NotImplementedError
