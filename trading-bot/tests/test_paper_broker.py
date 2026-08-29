import pandas as pd
import pytest

from src.broker.paper_broker import PaperBroker


def _candle(time, high, low):
    return pd.Series({"high": high, "low": low}, name=pd.Timestamp(time))


def test_buy_hits_take_profit():
    broker = PaperBroker(initial_balance=10_000)
    broker.open_position("BUY", size=2.0, entry_price=100.0, stop_loss=95.0, take_profit=110.0, timestamp=pd.Timestamp("2024-01-01"))

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=111.0, low=99.0))

    assert trade is not None
    assert trade.exit_reason == "take_profit"
    assert trade.pnl == pytest.approx(20.0)
    assert broker.position is None
    assert broker.balance == pytest.approx(10_020.0)


def test_buy_hits_stop_loss():
    broker = PaperBroker(initial_balance=10_000)
    broker.open_position("BUY", size=2.0, entry_price=100.0, stop_loss=95.0, take_profit=110.0, timestamp=pd.Timestamp("2024-01-01"))

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=101.0, low=90.0))

    assert trade.exit_reason == "stop_loss"
    assert trade.pnl == pytest.approx(-10.0)


def test_both_levels_in_range_assumes_stop_loss_first():
    broker = PaperBroker(initial_balance=10_000)
    broker.open_position("BUY", size=1.0, entry_price=100.0, stop_loss=95.0, take_profit=110.0, timestamp=pd.Timestamp("2024-01-01"))

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=115.0, low=90.0))

    assert trade.exit_reason == "stop_loss"


def test_sell_hits_take_profit():
    broker = PaperBroker(initial_balance=10_000)
    broker.open_position("SELL", size=1.0, entry_price=100.0, stop_loss=105.0, take_profit=90.0, timestamp=pd.Timestamp("2024-01-01"))

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=101.0, low=89.0))

    assert trade.exit_reason == "take_profit"
    assert trade.pnl == pytest.approx(10.0)


def test_no_position_returns_none():
    broker = PaperBroker(initial_balance=10_000)
    assert broker.update_open_position(_candle("2024-01-01", 100, 99)) is None


def test_daily_stats_filters_by_close_date():
    broker = PaperBroker(initial_balance=10_000)
    broker.open_position("BUY", size=1.0, entry_price=100.0, stop_loss=95.0, take_profit=110.0, timestamp=pd.Timestamp("2024-01-01"))
    broker.update_open_position(_candle("2024-01-01 00:05", high=111.0, low=99.0))

    trades, pnl = broker.daily_stats(pd.Timestamp("2024-01-01").date())
    assert trades == 1
    assert pnl == pytest.approx(10.0)

    trades, pnl = broker.daily_stats(pd.Timestamp("2024-01-02").date())
    assert trades == 0
    assert pnl == 0

