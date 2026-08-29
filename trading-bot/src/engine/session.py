"""The single per-candle decision loop shared by the backtest engine and the
live paper-trading engine, so both run exactly the same entry/exit rules.
"""
from __future__ import annotations

import logging

import pandas as pd

from ..broker.paper_broker import PaperBroker
from ..risk.risk_manager import RiskManager
from ..strategy.base import Strategy

logger = logging.getLogger(__name__)


class TradingSession:
    def __init__(self, strategy: Strategy, risk_manager: RiskManager, broker: PaperBroker) -> None:
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.broker = broker

    def process_candle(self, candle: pd.Series, history: pd.DataFrame) -> None:
        closed_trade = self.broker.update_open_position(candle)
        if closed_trade is not None:
            logger.info(
                "closed %s trade: entry=%.3f exit=%.3f pnl=%.2f (%s)",
                closed_trade.direction,
                closed_trade.entry_price,
                closed_trade.exit_price,
                closed_trade.pnl,
                closed_trade.exit_reason,
            )

        if self.broker.position is not None:
            return

        trades_today, pnl_today = self.broker.daily_stats(candle.name.date())
        if not self.risk_manager.can_trade(trades_today, pnl_today, self.broker.balance):
            return

        signal = self.strategy.on_candle(history)
        if signal.action not in ("BUY", "SELL"):
            return

        entry_price = candle["close"]
        atr_value = history["atr"].iloc[-1]
        if pd.isna(atr_value) or atr_value <= 0:
            return

        stop_loss, take_profit = self.risk_manager.compute_stop_take(signal.action, entry_price, atr_value)
        size = self.risk_manager.position_size(self.broker.balance, entry_price, stop_loss)
        if size <= 0:
            return

        self.broker.open_position(signal.action, size, entry_price, stop_loss, take_profit, candle.name)
        logger.info(
            "opened %s: entry=%.3f sl=%.3f tp=%.3f size=%.4f (%s)",
            signal.action,
            entry_price,
            stop_loss,
            take_profit,
            size,
            signal.reason,
        )
