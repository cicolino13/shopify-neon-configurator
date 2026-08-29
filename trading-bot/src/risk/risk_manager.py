"""Position sizing and daily risk limits.

Position sizing is intentionally simplified: it computes an abstract "unit"
size such that (size * stop_distance) equals the amount of account currency
risked on the trade. Real brokers quote instruments in lots/contracts with
their own contract size and margin rules (e.g. MT5's XAUUSD is typically
100 oz per standard lot) — when wiring this up to a real broker, convert
`size` into that broker's lot/contract units before placing any live order.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskManager:
    risk_per_trade_pct: float
    sl_atr_mult: float
    tp_atr_mult: float
    max_trades_per_day: int
    max_daily_loss_pct: float

    @classmethod
    def from_config(cls, risk_config) -> "RiskManager":
        """Build a RiskManager from a config.RiskConfig, ignoring fields (like
        initial_balance) that belong to the broker rather than the risk rules.
        """
        return cls(
            risk_per_trade_pct=risk_config.risk_per_trade_pct,
            sl_atr_mult=risk_config.sl_atr_mult,
            tp_atr_mult=risk_config.tp_atr_mult,
            max_trades_per_day=risk_config.max_trades_per_day,
            max_daily_loss_pct=risk_config.max_daily_loss_pct,
        )

    def compute_stop_take(self, action: str, entry_price: float, atr_value: float) -> tuple[float, float]:
        sl_distance = atr_value * self.sl_atr_mult
        tp_distance = atr_value * self.tp_atr_mult

        if action == "BUY":
            return entry_price - sl_distance, entry_price + tp_distance
        if action == "SELL":
            return entry_price + sl_distance, entry_price - tp_distance

        raise ValueError(f"unsupported action: {action}")

    def position_size(self, balance: float, entry_price: float, stop_loss_price: float) -> float:
        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance <= 0:
            return 0.0

        risk_amount = balance * (self.risk_per_trade_pct / 100.0)
        return risk_amount / stop_distance

    def can_trade(self, trades_today: int, pnl_today: float, balance: float) -> bool:
        if trades_today >= self.max_trades_per_day:
            return False

        max_loss = balance * (self.max_daily_loss_pct / 100.0)
        if pnl_today <= -max_loss:
            return False

        return True
