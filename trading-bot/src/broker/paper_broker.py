"""Simulated ("paper") broker: no real orders are ever placed. It tracks a
virtual balance and fills/closes positions purely against candle data, which
is what makes it safe to run against a live price feed for dry-run testing.

Candle prices are treated as **bid** (the MT5 convention); the CostModel
derives the ask from them, so a round trip pays spread + commission.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from .base import Position, Trade
from .costs import CostModel


class PaperBroker:
    def __init__(self, initial_balance: float, costs: CostModel | None = None) -> None:
        self.balance = initial_balance
        self.costs = costs if costs is not None else CostModel.zero()
        self.position: Optional[Position] = None
        self.trade_log: list[Trade] = []

    def open_position(
        self,
        direction: str,
        size: float,
        bid_price: float,
        stop_loss: float,
        take_profit: float,
        timestamp: datetime,
    ) -> None:
        """Open a position at the current bid quote. The actual entry price
        is derived from the cost model (a BUY pays the ask, plus slippage).
        Stop-loss and take-profit are absolute price levels, already computed
        from the entry fill by the risk manager.
        """
        if self.position is not None:
            raise RuntimeError("a position is already open")

        self.position = Position(
            direction=direction,
            size=size,
            entry_price=self.costs.entry_fill(direction, bid_price),
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=timestamp,
        )

    def update_open_position(self, candle: pd.Series) -> Optional[Trade]:
        """Check whether the current candle hits the open position's
        stop-loss or take-profit, close it if so, and return the resulting
        Trade (or None if nothing closed / no position open).

        A BUY is closed at the bid, so the raw candle high/low apply. A SELL
        is closed at the ask, so the spread is added to the candle before
        comparing -- which is why a short's stop is reached slightly earlier
        than the raw chart suggests.

        If both levels fall inside the same candle's range, the stop-loss is
        assumed to hit first -- a conservative, standard backtesting
        assumption since intra-candle order is unknown from OHLC data alone.
        """
        if self.position is None:
            return None

        pos = self.position
        timestamp = candle.name

        exit_price: float | None = None
        exit_reason: str | None = None

        if pos.direction == "BUY":
            exit_high, exit_low = candle["high"], candle["low"]
            if exit_low <= pos.stop_loss:
                exit_price = self.costs.stop_fill("BUY", pos.stop_loss)
                exit_reason = "stop_loss"
            elif exit_high >= pos.take_profit:
                exit_price = self.costs.limit_fill("BUY", pos.take_profit)
                exit_reason = "take_profit"
        else:  # SELL closes at the ask
            exit_high = candle["high"] + self.costs.spread
            exit_low = candle["low"] + self.costs.spread
            if exit_high >= pos.stop_loss:
                exit_price = self.costs.stop_fill("SELL", pos.stop_loss)
                exit_reason = "stop_loss"
            elif exit_low <= pos.take_profit:
                exit_price = self.costs.limit_fill("SELL", pos.take_profit)
                exit_reason = "take_profit"

        if exit_price is None:
            return None

        commission = self.costs.commission(pos.size)
        pnl = self._gross_pnl(pos, exit_price) - commission
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
            commission=commission,
        )
        self.trade_log.append(trade)
        self.position = None
        return trade

    def force_close(self, candle: pd.Series) -> Optional[Trade]:
        """Close any open position at the candle's closing quote. Used to
        flatten the book at the end of a backtest so unrealised PnL is not
        silently dropped from the results.
        """
        if self.position is None:
            return None

        pos = self.position
        close = candle["close"]
        # exit at the price the position would actually be closed at
        exit_price = close if pos.direction == "BUY" else close + self.costs.spread

        commission = self.costs.commission(pos.size)
        pnl = self._gross_pnl(pos, exit_price) - commission
        self.balance += pnl

        trade = Trade(
            direction=pos.direction,
            size=pos.size,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            opened_at=pos.opened_at,
            closed_at=candle.name,
            pnl=pnl,
            exit_reason="end_of_data",
            commission=commission,
        )
        self.trade_log.append(trade)
        self.position = None
        return trade

    def equity(self, bid_price: float) -> float:
        """Balance plus the open position marked to the price it would close
        at right now (net of the commission still owed).
        """
        if self.position is None:
            return self.balance

        pos = self.position
        exit_price = bid_price if pos.direction == "BUY" else bid_price + self.costs.spread
        return self.balance + self._gross_pnl(pos, exit_price) - self.costs.commission(pos.size)

    def daily_stats(self, date) -> tuple[int, float]:
        """(trades closed on `date`, sum of their pnl)."""
        todays = [t for t in self.trade_log if t.closed_at.date() == date]
        return len(todays), sum(t.pnl for t in todays)

    @staticmethod
    def _gross_pnl(pos: Position, price: float) -> float:
        direction_sign = 1 if pos.direction == "BUY" else -1
        return direction_sign * (price - pos.entry_price) * pos.size
