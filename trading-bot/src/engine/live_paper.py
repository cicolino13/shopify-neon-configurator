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
from ..indicators import add_indicators
from ..risk.risk_manager import RiskManager
from ..strategy.base import Strategy
from .session import TradingSession

logger = logging.getLogger(__name__)


def run_live_paper(config: BotConfig, strategy: Strategy, stop_after_iterations: int | None = None) -> PaperBroker:
    """Poll MT5 for new candles and run the paper-trading session forever
    (or `stop_after_iterations` polls, for testing).
    """
    feed = Mt5Feed(config.symbol, config.timeframe)
    risk_manager = RiskManager.from_config(config.risk)
    broker = PaperBroker(config.risk.initial_balance)
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
            df = feed.get_candles(config.live.history_bars)
            df = add_indicators(
                df,
                config.strategy.ema_fast,
                config.strategy.ema_slow,
                config.strategy.rsi_period,
                config.strategy.atr_period,
            )

            latest_candle = df.iloc[-1]
            if last_seen_time is None or latest_candle.name > last_seen_time:
                session.process_candle(latest_candle, df)
                last_seen_time = latest_candle.name
                logger.info(
                    "[%s] equity=%.2f open_position=%s",
                    datetime.now(timezone.utc).isoformat(),
                    broker.equity(latest_candle["close"]),
                    broker.position is not None,
                )

            iterations += 1
            time.sleep(config.live.poll_seconds)
    finally:
        feed.shutdown()

    return broker
