import pytest

from src.broker.costs import CostModel


def test_zero_model_has_no_costs():
    costs = CostModel.zero()
    assert costs.entry_fill("BUY", 2000.0) == 2000.0
    assert costs.entry_fill("SELL", 2000.0) == 2000.0
    assert costs.commission(10.0) == 0.0


def test_buy_enters_at_the_ask():
    costs = CostModel(spread=0.30)
    assert costs.entry_fill("BUY", 2000.0) == pytest.approx(2000.30)


def test_sell_enters_at_the_bid():
    costs = CostModel(spread=0.30)
    assert costs.entry_fill("SELL", 2000.0) == pytest.approx(2000.0)


def test_slippage_is_always_adverse_on_entry():
    costs = CostModel(spread=0.0, slippage=0.05)
    assert costs.entry_fill("BUY", 2000.0) == pytest.approx(2000.05)
    assert costs.entry_fill("SELL", 2000.0) == pytest.approx(1999.95)


def test_stops_slip_adversely_but_limits_do_not():
    costs = CostModel(slippage=0.05)

    assert costs.stop_fill("BUY", 1990.0) == pytest.approx(1989.95)
    assert costs.stop_fill("SELL", 2010.0) == pytest.approx(2010.05)

    assert costs.limit_fill("BUY", 2010.0) == pytest.approx(2010.0)
    assert costs.limit_fill("SELL", 1990.0) == pytest.approx(1990.0)


def test_commission_scales_with_size():
    costs = CostModel(commission_per_unit=0.07)
    assert costs.commission(100.0) == pytest.approx(7.0)
