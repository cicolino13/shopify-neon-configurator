"""Transaction cost model.

For short-timeframe scalping this is the single most important part of a
realistic backtest: a strategy that looks profitable on raw mid prices very
often turns negative once spread and commission are charged on every trade.

Price convention
----------------
MT5 candles for XAUUSD are **bid** prices, so throughout this project:

    ask = bid + spread

which means:
  * a BUY  enters at the ask and exits at the bid
  * a SELL enters at the bid and exits at the ask

so every round trip pays the spread once, in addition to commission.

Units
-----
`spread` and `slippage` are in price units of the instrument -- for XAUUSD
that is USD per troy ounce (e.g. 0.30 = 30 cents). `commission_per_unit` is
the round-turn commission per unit of position size, i.e. per ounce; if your
broker quotes commission per standard lot (100 oz), divide by 100.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    spread: float = 0.0
    commission_per_unit: float = 0.0
    slippage: float = 0.0

    @classmethod
    def zero(cls) -> "CostModel":
        """A frictionless model. Useful for unit tests and for showing how
        much of a strategy's edge is eaten by costs -- never for evaluating
        whether a strategy is actually viable.
        """
        return cls()

    def entry_fill(self, direction: str, bid_price: float) -> float:
        """Price actually paid/received when opening, given the bid quote.

        Slippage is applied adversely: a market order to buy fills a little
        higher than expected, a market order to sell a little lower.
        """
        if direction == "BUY":
            return bid_price + self.spread + self.slippage
        return bid_price - self.slippage

    def stop_fill(self, direction: str, stop_price: float) -> float:
        """Price actually realised when a stop-loss triggers.

        Stops become market orders, so they slip adversely -- this is what
        makes real stop-losses cost slightly more than their nominal level.
        """
        if direction == "BUY":
            return stop_price - self.slippage
        return stop_price + self.slippage

    def limit_fill(self, direction: str, limit_price: float) -> float:
        """Price realised when a take-profit triggers. Limit orders fill at
        their level or not at all, so no adverse slippage is applied.
        """
        return limit_price

    def commission(self, size: float) -> float:
        """Round-turn commission charged once per completed trade."""
        return self.commission_per_unit * size
