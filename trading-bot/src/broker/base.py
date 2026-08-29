from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Direction = Literal["BUY", "SELL"]
ExitReason = Literal["stop_loss", "take_profit", "end_of_data"]


@dataclass
class Position:
    direction: Direction
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    opened_at: datetime


@dataclass
class Trade:
    direction: Direction
    size: float
    entry_price: float
    exit_price: float
    opened_at: datetime
    closed_at: datetime
    pnl: float
    exit_reason: ExitReason
    commission: float = 0.0
