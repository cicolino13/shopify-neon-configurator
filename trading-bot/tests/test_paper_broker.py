import pandas as pd
import pytest

from src.broker.costs import CostModel
from src.broker.paper_broker import PaperBroker


def _candle(time, high, low, close=None):
    data = {"high": high, "low": low}
    data["close"] = close if close is not None else (high + low) / 2
    return pd.Series(data, name=pd.Timestamp(time))


def _broker(costs=None):
    return PaperBroker(initial_balance=10_000, costs=costs)


def _open(broker, direction="BUY", size=2.0, bid=100.0, sl=95.0, tp=110.0):
    broker.open_position(direction, size, bid, sl, tp, pd.Timestamp("2024-01-01"))


# --------------------------------------------------------------------------
# frictionless behaviour
# --------------------------------------------------------------------------

def test_buy_hits_take_profit():
    broker = _broker()
    _open(broker)

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=111.0, low=99.0))

    assert trade.exit_reason == "take_profit"
    assert trade.pnl == pytest.approx(20.0)
    assert broker.position is None
    assert broker.balance == pytest.approx(10_020.0)


def test_buy_hits_stop_loss():
    broker = _broker()
    _open(broker)

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=101.0, low=90.0))

    assert trade.exit_reason == "stop_loss"
    assert trade.pnl == pytest.approx(-10.0)


def test_both_levels_in_range_assumes_stop_loss_first():
    broker = _broker()
    _open(broker, size=1.0)

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=115.0, low=90.0))

    assert trade.exit_reason == "stop_loss"


def test_sell_hits_take_profit():
    broker = _broker()
    _open(broker, direction="SELL", size=1.0, sl=105.0, tp=90.0)

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=101.0, low=89.0))

    assert trade.exit_reason == "take_profit"
    assert trade.pnl == pytest.approx(10.0)


def test_no_position_returns_none():
    assert _broker().update_open_position(_candle("2024-01-01", 100, 99)) is None


def test_cannot_open_two_positions():
    broker = _broker()
    _open(broker)
    with pytest.raises(RuntimeError):
        _open(broker)


# --------------------------------------------------------------------------
# costs
# --------------------------------------------------------------------------

def test_buy_entry_pays_the_spread():
    broker = _broker(CostModel(spread=0.50))
    _open(broker, size=1.0, bid=100.0)

    assert broker.position.entry_price == pytest.approx(100.50)


def test_spread_turns_a_nominally_flat_buy_into_a_loss():
    """Entering at the ask and exiting at the bid costs the spread even if
    the market never moves -- the core reason scalping is hard."""
    broker = _broker(CostModel(spread=0.50))
    _open(broker, size=1.0, bid=100.0, sl=99.0, tp=100.5)

    # market rises just enough to touch the take-profit at the bid
    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=100.5, low=100.0))

    assert trade.exit_reason == "take_profit"
    # bought at 100.50, sold at 100.50 -> exactly flat despite a 0.5 move up
    assert trade.pnl == pytest.approx(0.0)


def test_short_stop_triggers_earlier_because_it_closes_at_the_ask():
    broker = _broker(CostModel(spread=0.50))
    _open(broker, direction="SELL", size=1.0, bid=100.0, sl=101.0, tp=95.0)

    # bid high of 100.60 -> ask high of 101.10, which is past the 101.0 stop
    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=100.60, low=99.0))

    assert trade is not None
    assert trade.exit_reason == "stop_loss"


def test_commission_is_deducted_from_pnl():
    broker = _broker(CostModel(commission_per_unit=0.10))
    _open(broker, size=2.0)

    trade = broker.update_open_position(_candle("2024-01-01 00:01", high=111.0, low=99.0))

    assert trade.commission == pytest.approx(0.20)
    assert trade.pnl == pytest.approx(20.0 - 0.20)


# --------------------------------------------------------------------------
# bookkeeping
# --------------------------------------------------------------------------

def test_force_close_settles_an_open_position():
    broker = _broker()
    _open(broker, size=1.0, bid=100.0)

    trade = broker.force_close(_candle("2024-01-01 00:05", high=106.0, low=104.0, close=105.0))

    assert trade.exit_reason == "end_of_data"
    assert trade.pnl == pytest.approx(5.0)
    assert broker.position is None


def test_equity_marks_an_open_position_to_market():
    broker = _broker()
    _open(broker, size=2.0, bid=100.0)

    assert broker.equity(105.0) == pytest.approx(10_010.0)
    assert broker.equity(100.0) == pytest.approx(10_000.0)


def test_daily_stats_filters_by_close_date():
    broker = _broker()
    _open(broker, size=1.0)
    broker.update_open_position(_candle("2024-01-01 00:05", high=111.0, low=99.0))

    trades, pnl = broker.daily_stats(pd.Timestamp("2024-01-01").date())
    assert trades == 1
    assert pnl == pytest.approx(10.0)

    trades, pnl = broker.daily_stats(pd.Timestamp("2024-01-02").date())
    assert trades == 0
    assert pnl == 0
