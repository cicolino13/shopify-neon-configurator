"""Tests for the live paper-trading loop, driven by a stub feed so they run
anywhere -- the real MT5 feed is Windows-only.
"""
from __future__ import annotations

import pandas as pd

from src.broker.costs import CostModel
from src.config import BotConfig, LiveConfig, RiskConfig, StrategyConfig
from src.engine.live_paper import run_live_paper
from src.strategy.ema_rsi_scalper import EmaRsiScalper

from tests.helpers import make_choppy_candles


class StubFeed:
    """Replays a fixed candle set, revealing one more bar on each poll so the
    last bar is always the still-forming one, as MT5 behaves.
    """

    def __init__(self, candles: pd.DataFrame, start: int = 300) -> None:
        self.candles = candles
        self.cursor = start
        self.shutdown_called = False
        self.requested_counts: list[int] = []

    def get_candles(self, count: int) -> pd.DataFrame:
        self.requested_counts.append(count)
        window = self.candles.iloc[: self.cursor]
        self.cursor = min(self.cursor + 1, len(self.candles))
        return window.iloc[-count:]

    def shutdown(self) -> None:
        self.shutdown_called = True


def _config(poll_seconds: int = 0) -> BotConfig:
    return BotConfig(
        symbol="XAUUSD",
        timeframe="M1",
        strategy=StrategyConfig(name="ema_rsi_scalper", params={}),
        risk=RiskConfig(
            initial_balance=10_000.0,
            atr_period=14,
            risk_per_trade_pct=1.0,
            sl_atr_mult=1.5,
            tp_atr_mult=2.5,
            max_trades_per_day=50,
            max_daily_loss_pct=100.0,
        ),
        costs=CostModel(spread=0.30),
        live=LiveConfig(poll_seconds=poll_seconds, history_bars=300),
    )


def test_live_paper_runs_and_shuts_the_feed_down():
    feed = StubFeed(make_choppy_candles(n=1000))

    broker = run_live_paper(_config(), EmaRsiScalper(), stop_after_iterations=50, feed=feed)

    assert feed.shutdown_called
    assert feed.requested_counts == [300] * 50
    assert broker.balance > 0


def test_live_paper_never_acts_on_the_still_forming_candle():
    """The most recent MT5 bar is not final; trading on it would use a close
    price that can still change -- an easy way to make live results look
    better than they can ever be.
    """
    candles = make_choppy_candles(n=1000)
    feed = StubFeed(candles, start=300)

    broker = run_live_paper(_config(), EmaRsiScalper(), stop_after_iterations=100, feed=feed)

    # the loop saw bars up to index 399; the newest of those is never traded
    newest_seen = candles.index[398]
    assert broker.trade_log, "expected the stub feed to produce trades"
    for trade in broker.trade_log:
        assert trade.opened_at < newest_seen


def test_live_paper_shuts_the_feed_down_even_if_the_loop_raises():
    class ExplodingFeed(StubFeed):
        def get_candles(self, count: int) -> pd.DataFrame:
            raise RuntimeError("connection lost")

    feed = ExplodingFeed(make_choppy_candles(n=1000))

    try:
        run_live_paper(_config(), EmaRsiScalper(), stop_after_iterations=1, feed=feed)
    except RuntimeError:
        pass

    assert feed.shutdown_called
