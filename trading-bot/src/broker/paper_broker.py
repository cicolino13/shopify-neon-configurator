"""Simulated ("paper") broker: no real orders are ever placed. It tracks a
virtual balance and fills/closes positions purely against candle data, which
is what makes it safe to run against a live price feed for dry-run testing.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from .base import Position, Trade


class PaperBroker:
    def __init__(self, initial_balance: float) -> None:
        self.balance = initial_balance
        self.position: Optional[Position] = None
        self.trade_log: list[Trade] = []

    def open_position(
        self,
        direction: str,
        size: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        timestamp: datetime,
    ) -> None:
        if self.position is not None:
            raise RuntimeError("a position is already open")

        self.position = Position(
            direction=direction,
            size=size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=timestamp,
        )

    def update_open_position(self, candle: pd.Series) -> Optional[Trade]:
        """Check whether the current candle's high/low hits the open
        position's stop-loss or take-profit, close it if so, and return the
        resulting Trade (or None if nothing closed / no position open).

        If both levels fall inside the same candle's range, the stop-loss is
        assumed to hit first -- a conservative, standard backtesting
        assumption since intra-candle order is unknown from OHLC data alone.
        """
        if self.position is None:
            return None

        pos = self.position
        high, low, timestamp = candle["high"], candle["low"], candle.name

        exit_price = None
        exit_reason = None

        if pos.direction == "BUY":
            if low <= pos.stop_loss:
                exit_price, exit_reason = pos.stop_loss, "stop_loss"
            elif high >= pos.take_profit:
                exit_price, exit_reason = pos.take_profit, "take_profit"
        else:  # SELL
            if high >= pos.stop_loss:
                exit_price, exit_reason = pos.stop_loss, "stop_loss"
            elif low <= pos.take_profit:
                exit_price, exit_reason = pos.take_profit, "take_profit"

        if exit_price is None:
            return None

        pnl = self._pnl(pos, exit_price)
        self.balance += pnl

        trade = Trade(
            direction=pos.direction,
            size=pos.size,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            opened_at=pos.opened_at,
            closed_at=timestamp,
            pnl=pnl,
            exit_reason=exit_reason,
        )
        self.trade_log.append(trade)
        self.position = None
        return trade

    def equity(self, current_price: float) -> float:
        if self.position is None:
            return self.balance
        return self.balance + self._pnl(self.position, current_price)

    def daily_stats(self, date) -> tuple[int, float]:
        """(trades closed on `date`, sum of their pnl)."""
        todays = [t for t in self.trade_log if t.closed_at.date() == date]
        return len(todays), sum(t.pnl for t in todays)

    @staticmethod
    def _pnl(pos: Position, price: float) -> float:
        direction_sign = 1 if pos.direction == "BUY" else -1
        return direction_sign * (price - pos.entry_price) * pos.size
