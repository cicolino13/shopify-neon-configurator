"""Runs the trading session against live MT5 market data, but only ever
simulates order execution via PaperBroker -- no real money is ever at risk
running this engine. It is the intended way to "dry run" a strategy against
real-time prices before ever considering live execution.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from ..broker.paper_broker import PaperBroker
from ..config import BotConfig
from ..data.mt5_feed import Mt5Feed
from ..engine.backtest import prepare_candles
from ..risk.risk_manager import RiskManager
from ..strategy.base import Strategy
from .session import TradingSession

logger = logging.getLogger(__name__)


def run_live_paper(
    config: BotConfig,
    strategy: Strategy,
    stop_after_iterations: int | None = None,
    feed=None,
) -> PaperBroker:
    """Poll MT5 for new candles and run the paper-trading session forever
    (or `stop_after_iterations` polls, for testing).

    `feed` may be supplied by the caller (an already-connected Mt5Feed, or a
    stub in tests); otherwise one is created from the config.
    """
    feed = feed if feed is not None else Mt5Feed(config.symbol, config.timeframe)
    risk_manager = RiskManager.from_config(config.risk)
    broker = PaperBroker(config.risk.initial_balance, config.costs)
    session = TradingSession(strategy, risk_manager, broker)

    logger.warning(
        "Starting LIVE PAPER trading on %s/%s -- this uses real market data "
        "but places NO real orders. Balance is simulated.",
        config.symbol,
        config.timeframe,
    )

    last_seen_time = None
    iterations = 0

    try:
        while stop_after_iterations is None or iterations < stop_after_iterations:
            df = prepare_candles(feed.get_candles(config.live.history_bars), strategy, config.risk.atr_period)

            # Act on the last *closed* candle: the most recent bar from MT5 is
            # still forming, and trading on it would use a close price that is
            # not final -- a subtle way to make a backtest look better than
            # reality ever will.
            if len(df) >= 2:
                closed_candle = df.iloc[-2]
                if last_seen_time is None or closed_candle.name > last_seen_time:
                    session.process_candle(closed_candle, df.iloc[:-1])
                    last_seen_time = closed_candle.name
                    logger.info(
                        "[%s] equity=%.2f open_position=%s",
                        datetime.now(timezone.utc).isoformat(),
                        broker.equity(closed_candle["close"]),
                        broker.position is not None,
                    )

            iterations += 1
            time.sleep(config.live.poll_seconds)
    finally:
        feed.shutdown()

    return broker
